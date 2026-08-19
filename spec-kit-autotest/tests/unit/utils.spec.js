/**
 * 工具层单元测试：这些路径不会被远端 E2E 覆盖，但会直接影响所有接口/UI 用例。
 */
const { test, expect } = require('@playwright/test');
const env = require('../../config/env');
const { ApiClient, assertOk } = require('../../utils/apiClient');
const { apiLogin } = require('../../utils/auth');
const { classifyEnvironmentFailure } = require('../../utils/envGuard');
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

  test('assertOk 返回 data，异常结构抛出可诊断错误', async () => {
    expect(assertOk(response(200, { ok: true, data: { id: 1 } }), { ok: true, data: { id: 1 } })).toEqual({ id: 1 });
    expect(() => assertOk(response(500, { ok: false }), { ok: false })).toThrow(/HTTP 500/);
  });
});

test.describe('环境分类与资源清理', () => {
  test('503 和 HTML 响应被分类为 ENV_ERROR', () => {
    const err = classifyEnvironmentFailure('SDD', {
      status: () => 503, headers: () => ({ 'content-type': 'text/html' }),
    });
    expect(err.classification).toBe('ENV_ERROR');
  });

  test('ResourceTracker 逆序清理并接受 404', async () => {
    const order = [];
    const tracker = new ResourceTracker();
    tracker.track({ type: 'requirement', id: '1', cleanup: async () => { order.push('1'); return response(204, {}); } });
    tracker.track({ type: 'sdd', id: '2', cleanup: async () => { order.push('2'); return response(404, {}); } });
    await tracker.cleanupAll();
    expect(order).toEqual(['2', '1']);
  });

  test('ResourceTracker 报告残留资源', async () => {
    const tracker = new ResourceTracker();
    tracker.track({ type: 'requirement', id: 'bad', cleanup: async () => response(503, {}) });
    await expect(tracker.cleanupAll()).rejects.toThrow(/bad/);
  });

  test('safeCleanup 不再静默吞掉清理失败', async () => {
    await expect(safeCleanup('requirement:bad', async () => response(503, {}))).rejects.toThrow(/HTTP 503/);
    await expect(safeCleanup('requirement:ok', async () => response(404, {}))).resolves.toBeTruthy();
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
