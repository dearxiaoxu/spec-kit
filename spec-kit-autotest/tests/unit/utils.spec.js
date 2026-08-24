/**
 * 工具层单元测试：这些路径不会被远端 E2E 覆盖，但会直接影响所有接口/UI 用例。
 */
const { test, expect } = require('@playwright/test');
const env = require('../../config/env');
const { ApiClient, assertOk } = require('../../utils/apiClient');
const { apiLogin } = require('../../utils/auth');
const { EnvironmentResponseError, classifyEnvironmentFailure, envTolerant } = require('../../utils/envGuard');
const { ResourceTracker, safeCleanup } = require('../../utils/resourceTracker');
const {
  ts, uniqueTitle, requirementData, taskData, sddProjectData, docPayload,
} = require('../../utils/testData');

function response(status, body) {
  return { status: () => status, json: async () => body };
}

test.describe('环境与测试数据工具', () => {
  test('env.api 统一拼接 API 前缀', () => {
    expect(env.api('/auth/login')).toBe('/api/v1/auth/login');
    expect(env.api('/requirements')).toMatch(/^\/api\/v1\//);
  });

  test('时间戳与标题生成器返回非空且带业务前缀', () => {
    expect(ts()).toMatch(/^[a-z0-9]+$/);
    expect(uniqueTitle('需求')).toMatch(/^\[测试\]需求-/);
  });

  test('各类数据生成器支持覆盖默认字段', () => {
    expect(requirementData({ title: '覆盖', urgency: 5 })).toMatchObject({ title: '覆盖', urgency: 5 });
    expect(taskData({ priority: 'P1' })).toMatchObject({ priority: 'P1', dueDate: null });
    expect(sddProjectData({ name: '项目' })).toMatchObject({ name: '项目' });
    const doc = docPayload({ name: 'a.md' });
    expect(doc).toMatchObject({ name: 'a.md', mimeType: 'text/markdown' });
    expect(Buffer.isBuffer(doc.buffer)).toBe(true);
  });

  test('需求数据生成器提供完整且精确的默认值', () => {
    const data = requirementData();
    expect(data.title).toMatch(/^\[测试\]需求-[a-z0-9]+$/);
    expect(data).toEqual({
      title: data.title,
      description: '测试用需求描述',
      acceptanceCriteria: '验收标准：流程可正常流转',
      businessBackground: '测试用业务背景描述',
      businessGoal: '测试目标',
      nonGoals: '非目标',
      userRoles: '测试人员',
      coreFlow: '核心流程',
      dataScope: '数据范围',
      interfaceImpact: '接口影响',
      boundaryConditions: '边界条件',
      riskPoints: '风险点',
      category: 'feature',
      urgency: 3,
      importance: 3,
      estimatedCfp: 0,
      requirementLevel: '',
      forceFullSdd: false,
      source: 'internal',
      reviewerId: '',
    });
  });

  test('其他数据生成器默认值和文档内容稳定', () => {
    const task = taskData();
    expect(task.title).toMatch(/^\[测试\]待办-/);
    expect(task).toEqual({ title: task.title, priority: 'P2', dueDate: null });
    const sdd = sddProjectData();
    expect(sdd.name).toMatch(/^\[测试\]SDD项目-/);
    expect(sdd).toEqual({ name: sdd.name, description: '测试用规范驱动项目' });
    const doc = docPayload();
    expect(doc.name).toMatch(/^\[测试\]文档-.*\.md$/);
    expect(doc.mimeType).toBe('text/markdown');
    expect(doc.buffer.toString('utf-8')).toBe('# 测试文档\n\n这是自动测试生成的文档内容。');
  });
});

test.describe('ApiClient', () => {
  test('默认请求头包含 JSON，设置 token 后带 Bearer', async () => {
    const client = new ApiClient({});
    expect(client.headers()).toEqual({ 'Content-Type': 'application/json' });
    client.setTokens('access', 'refresh');
    expect(client.headers({ 'X-Test': 'yes' })).toMatchObject({
      Authorization: 'Bearer access', 'X-Test': 'yes',
    });
  });

  test('GET 收到 401 时原样返回且不伪刷新', async () => {
    const calls = [];
    const request = {
      get: async (url) => {
        calls.push(['get', url]);
        return response(401, { ok: false });
      },
    };
    const client = new ApiClient(request);
    client.setTokens('expired', 'refresh');
    const res = await client.get('https://example.test/resource', { params: { page: 1 } });
    expect(res.status()).toBe(401);
    expect(calls.map(([, url]) => url)).toEqual(['https://example.test/resource']);
  });

  test('POST 收到 401 不会循环重试', async () => {
    let count = 0;
    const client = new ApiClient({ post: async () => { count += 1; return response(401, {}); } });
    client.setTokens('expired', 'refresh');
    await client.post('/endpoint', { data: {} });
    expect(count).toBe(1);
  });

  test('各 HTTP 动词与请求选项完整透传', async () => {
    const calls = [];
    const request = Object.fromEntries(['get', 'post', 'put', 'patch', 'delete'].map((method) => [
      method,
      async (url, options) => { calls.push({ method, url, options }); return response(204, {}); },
    ]));
    const client = new ApiClient(request);
    client.setTokens('access', 'refresh');
    for (const method of ['get', 'post', 'put', 'patch', 'delete']) {
      await client[method](`/v1/${method}`, { data: { method }, params: { page: 2 }, headers: { 'X-Test': method } });
    }
    expect(calls.map(({ method }) => method)).toEqual(['get', 'post', 'put', 'patch', 'delete']);
    for (const call of calls) {
      expect(call.url).toBe(`/v1/${call.method}`);
      expect(call.options.data).toEqual({ method: call.method });
      expect(call.options.params).toEqual({ page: 2 });
      expect(call.options.headers).toEqual({
        'Content-Type': 'application/json', Authorization: 'Bearer access', 'X-Test': call.method,
      });
    }
  });

  test('自定义请求头可覆盖默认值', async () => {
    let options;
    const client = new ApiClient({ get: async (_url, value) => { options = value; return response(200, {}); } });
    await client.get('/resource', { headers: { 'Content-Type': 'text/plain' } });
    expect(options.headers).toEqual({ 'Content-Type': 'text/plain' });
  });

  test('assertOk 返回 data，异常结构抛出可诊断错误', async () => {
    expect(assertOk(response(200, { ok: true, data: { id: 1 } }), { ok: true, data: { id: 1 } })).toEqual({ id: 1 });
    expect(() => assertOk(response(500, { ok: false }), { ok: false })).toThrow(/HTTP 500/);
    expect(() => assertOk(response(502, null), null)).toThrow(/HTTP 502/);
    expect(() => assertOk(response(400, {}), { ok: false, reason: 'bad-input' })).toThrow(/bad-input/);
  });
});

test.describe('环境分类与资源清理', () => {
  test('503 和 HTML 响应被分类为 ENV_ERROR', () => {
    const err = classifyEnvironmentFailure('SDD', {
      status: () => 503, headers: () => ({ 'content-type': 'text/html' }),
    });
    expect(err.classification).toBe('ENV_ERROR');
    expect(err).toBeInstanceOf(EnvironmentResponseError);
    expect(err.name).toBe('EnvironmentResponseError');
    expect(err.status).toBe(503);
    expect(err.isHtml).toBe(true);
    expect(err.message).toBe('[env] SDD 返回 503 HTML页');
  });

  test('环境错误按状态码或 HTML 独立分类，并守住 500 边界', () => {
    const json503 = classifyEnvironmentFailure('JSON服务', response(503, {}));
    expect(json503).toMatchObject({ status: 503, isHtml: false, classification: 'ENV_ERROR' });
    const html200 = classifyEnvironmentFailure('HTML服务', {
      status: () => 200, headers: () => ({ 'content-type': 'Text/HTML; charset=utf-8' }),
    });
    expect(html200).toMatchObject({ status: 200, isHtml: true, classification: 'ENV_ERROR' });
    expect(classifyEnvironmentFailure('边界499', response(499, {}))).toBeNull();
    expect(classifyEnvironmentFailure('边界500', response(500, {}))).toMatchObject({ status: 500 });
  });

  test('环境分类兼容缺失响应字段且 envTolerant 只在异常时抛出', () => {
    expect(classifyEnvironmentFailure('无响应', null)).toBeNull();
    expect(classifyEnvironmentFailure('无响应头', { status: () => 200 })).toBeNull();
    expect(envTolerant('正常', response(200, {}))).toBe(false);
    expect(() => envTolerant('异常', response(500, {}))).toThrow(EnvironmentResponseError);
  });

  test('ResourceTracker 逆序清理并接受 404', async () => {
    const order = [];
    const tracker = new ResourceTracker();
    tracker.track({ type: 'requirement', id: '1', cleanup: async () => { order.push('1'); return response(204, {}); } });
    tracker.track({ type: 'sdd', id: '2', cleanup: async () => { order.push('2'); return response(404, {}); } });
    await tracker.cleanupAll();
    expect(order).toEqual(['2', '1']);
    expect(tracker.resources).toEqual([]);
    expect(tracker.cleanupFailures).toEqual([]);
  });

  test('ResourceTracker 拒绝不完整登记并返回已登记 ID', () => {
    const tracker = new ResourceTracker();
    expect(() => tracker.track({ id: '1', cleanup: async () => {} })).toThrow(/type、id 和 cleanup/);
    expect(() => tracker.track({ type: 'sdd', cleanup: async () => {} })).toThrow(/type、id 和 cleanup/);
    expect(() => tracker.track({ type: 'sdd', id: '1', cleanup: 'nope' })).toThrow(/type、id 和 cleanup/);
    expect(tracker.track({ type: 'sdd', id: 'ok', title: '项目', cleanup: async () => response(204, {}) })).toBe('ok');
  });

  test('ResourceTracker 接受所有清理成功状态和空响应', async () => {
    for (const status of [200, 202, 204, 404]) {
      const tracker = new ResourceTracker();
      tracker.track({ type: 'sdd', id: String(status), cleanup: async () => response(status, {}) });
      await expect(tracker.cleanupAll()).resolves.toBeUndefined();
    }
    const tracker = new ResourceTracker();
    tracker.track({ type: 'sdd', id: 'empty', cleanup: async () => undefined });
    await expect(tracker.cleanupAll()).resolves.toBeUndefined();
    const noStatus = new ResourceTracker();
    noStatus.track({ type: 'sdd', id: 'no-status', cleanup: async () => ({}) });
    await expect(noStatus.cleanupAll()).resolves.toBeUndefined();
  });

  test('ResourceTracker 遇到失败继续清理并保留完整失败元数据', async () => {
    const order = [];
    const tracker = new ResourceTracker();
    tracker.track({ type: 'requirement', id: 'ok', cleanup: async () => { order.push('ok'); return response(204, {}); } });
    tracker.track({ type: 'sdd', id: 'bad', title: '坏项目', cleanup: async () => { order.push('bad'); throw new Error('network down'); } });
    await expect(tracker.cleanupAll()).rejects.toThrow(/network down/);
    expect(order).toEqual(['bad', 'ok']);
    expect(tracker.cleanupFailures).toEqual([{ type: 'sdd', id: 'bad', title: '坏项目', error: 'network down' }]);
    expect(tracker.resources).toEqual([]);
  });

  test('ResourceTracker 报告残留资源', async () => {
    const tracker = new ResourceTracker();
    tracker.track({ type: 'requirement', id: 'bad', cleanup: async () => response(503, {}) });
    await expect(tracker.cleanupAll()).rejects.toThrow(/bad.*HTTP 503/);
    expect(tracker.cleanupFailures[0].title).toBe('');
  });

  test('safeCleanup 不再静默吞掉清理失败', async () => {
    await expect(safeCleanup('requirement:bad', async () => response(503, {}))).rejects.toThrow(/HTTP 503/);
    await expect(safeCleanup('requirement:ok', async () => response(404, {}))).resolves.toBeTruthy();
    await expect(safeCleanup('sdd:throw', async () => { throw new Error('socket closed'); })).rejects.toThrow(/sdd:throw.*socket closed/);
    const accepted = response(202, {});
    await expect(safeCleanup('sdd:accepted', async () => accepted)).resolves.toBe(accepted);
    await expect(safeCleanup('sdd:empty', async () => undefined)).resolves.toBeUndefined();
    await expect(safeCleanup('sdd:no-status', async () => ({}))).resolves.toEqual({});
  });
});

test.describe('apiLogin', () => {
  test('成功登录后保存双 token', async () => {
    const request = {
      post: async (url, opts) => {
        expect(url).toBe(`${env.baseURL}${env.api('/auth/login')}`);
        expect(opts.data.username).toBe('tester');
        return response(200, {
          ok: true,
          data: { accessToken: 'a', refreshToken: 'r', user: { username: 'tester' } },
        });
      },
    };
    const client = await apiLogin(request, { username: 'tester', password: 'secret' });
    expect(client.accessToken).toBe('a');
    expect(client.refreshToken).toBe('r');
  });

  test('登录失败抛出包含 HTTP 状态的错误', async () => {
    const request = { post: async () => response(401, { ok: false, message: 'bad' }) };
    await expect(apiLogin(request, { username: 'tester', password: 'bad' })).rejects.toThrow(/HTTP 401/);
  });
});
