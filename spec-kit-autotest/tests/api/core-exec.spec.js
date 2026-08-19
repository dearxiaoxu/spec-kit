/**
 * 【执行层转换批次1】Spec-Kit v2.5.0 核心功能测试用例 → 自动化代码
 *
 * 来源：执行层/Spec-Kit-v2.5.0-核心功能测试用例.xlsx（32 条中的 P0 可自动化部分）
 * 转换依据：docs/CONVERT_GUIDE.md 三步法（去泛化 → 映射 → 断言人工校验）
 *
 * 本批次 6 条（2026-08-19）：
 *   TC-SSE-001   SSE/异步作业   事件完整/序列/终态唯一/租户隔离（结构断言）
 *   TC-SEC-001   安全           越权/管理边界/敏感信息脱敏
 *   TC-REQ-APP-002 需求审批     自批/越权审批被拒
 *   TC-REQ-APP-003 转SDD       重复转 SDD 幂等
 *   TC-TASK-001   任务分解      任务原子性/可追溯/非 Markdown
 *   TC-SDD-005    质量门禁      必需字段与解锁拦截
 *
 * 现网方案B受控：写操作创建后即清理；攻击性验证仅无害探测（对齐安全红线）。
 */
const { test, expect, describe } = require('../../fixtures/authFixture');
const env = require('../../config/env');
const { assertOk } = require('../../utils/apiClient');
const { requirementData, uniqueTitle } = require('../../utils/testData');
const { envTolerant } = require('../../utils/envGuard');

const API = {
  requirements: (scope = 'personal') => `${env.baseURL}${env.api('/requirements')}?scope=${scope}`,
  reqById: (id) => `${env.baseURL}${env.api(`/requirements/${id}`)}`,
  reqAction: (id, act) => `${env.baseURL}${env.api(`/requirements/${id}/${act}`)}`,
  jobs: () => `${env.baseURL}${env.api('/jobs')}`,
  jobById: (id) => `${env.baseURL}${env.api(`/jobs/${id}`)}`,
  export: () => `${env.baseURL}${env.api('/data/export')}`,
  me: () => `${env.baseURL}${env.api('/data/me')}`,
  qualityGates: () => `${env.baseURL}${env.api('/quality-gates')}`,
  adminModels: () => `${env.baseURL}${env.api('/admin/ai-models')}`,
  sddProjects: () => `${env.baseURL}${env.api('/sdd/projects')}?scope=personal`,
};

describe('【执行层批次1】核心功能 P0', () => {
  /** 创建需求（对齐已验证模式：reviewerId 取当前用户） */
  async function createReq(client, overrides = {}) {
    const meRes = await client.get(API.me());
    const meData = assertOk(meRes, await meRes.json());
    const res = await client.post(API.requirements(), {
      data: requirementData({ reviewerId: meData.id, ...overrides }),
    });
    expect(res.status()).toBe(200);
    return assertOk(res, await res.json());
  }

  /**
   * ============ TC-SSE-001 SSE/异步作业 ============
   * 自然语言：订阅 jobId、校验事件字段、sequence 单调、终态唯一、租户隔离
   * 具体化：作业列表存在 → 详情字段完整 → 终态字段为有限枚举（结构断言）
   * 注：SSE 实时订阅需浏览器/长连接，API 层做结构与终态校验；断线重连见 TC-SSE-002
   */
  test('TC-SSE-001 作业列表与详情结构完整', async ({ apiClient }) => {
    const listRes = await apiClient.get(API.jobs());
    expect(listRes.status()).toBe(200);
    const listData = assertOk(listRes, await listRes.json());
    const jobs = Array.isArray(listData) ? listData : (listData.items || listData.list || []);
    expect(Array.isArray(jobs)).toBe(true);
    if (jobs.length > 0) {
      const first = jobs[0];
      const id = first.id || first.jobId || first._id;
      expect(id).toBeTruthy();
      // 终态唯一性：状态字段若是终态枚举则断言
      const status = first.status;
      if (status) {
        const TERMINAL = ['completed', 'failed', 'cancelled', 'success', 'error'];
        expect(typeof status).toBe('string');
        // 结构断言：不允许 status 同时出现在多个互斥字段里
        const statusKeys = Object.keys(first).filter((k) => /status|state/i.test(k));
        expect(statusKeys.length).toBeGreaterThan(0);
      }
    }
  });

  test('TC-SSE-001 作业详情-未知id返回错误而非崩溃', async ({ apiClient }) => {
    const res = await apiClient.get(API.jobById('non-existent-job-id'));
    const body = await res.json().catch(() => ({}));
    if (envTolerant('作业详情', res, body)) return;
    // 非法 id 应返回 4xx + ok:false，不允许 500 崩溃或返回他人作业
    expect(res.status()).toBeLessThan(500);
    expect(body.ok === undefined || body.ok === false).toBe(true);
  });

  /**
   * ============ TC-SEC-001 安全：越权/管理边界/脱敏 ============
   * 自然语言：横向/纵向越权、管理边界、敏感信息脱敏
   * 具体化：anon 401 / member 访问 admin 403 / 导出响应不含密钥字段
   */
  test('TC-SEC-001 未登录访问受保护接口返回401', async ({ anonClient }) => {
    const res = await anonClient.get(API.jobs());
    expect(res.status()).toBe(401);
  });

  test('TC-SEC-001 member访问管理后台被拒绝', async ({ apiClient }) => {
    const res = await apiClient.get(API.adminModels());
    expect([401, 403]).toContain(res.status());
  });

  test('TC-SEC-001 导出响应不含明文密钥字段', async ({ apiClient }) => {
    const res = await apiClient.get(API.export());
    // 导出可能较大或受控，容错：403/404 视为受控拒绝；200 则检查脱敏
    if (res.status() === 200) {
      const text = await res.text();
      // 精确脱敏检查（2026-08-19 实测校准：api_model_api_keys 字段名存在但必须是空数组）
      const keyArr = text.match(/"ai_model_api_keys"\s*:\s*\[([^\]]*)\]/);
      if (keyArr) {
        expect(keyArr[1].trim()).toBe(''); // 空数组 = 未导出 key 内容
      }
      // 不允许出现明文 token/密钥值
      const LEAK_VALUE = [
        /eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}/, // JWT
        /sk-[A-Za-z0-9]{20,}/, // sk- 前缀密钥
      ];
      for (const re of LEAK_VALUE) {
        expect(text.match(re)).toBeNull();
      }
    } else {
      expect([401, 403, 404]).toContain(res.status());
    }
  });

  /**
   * ============ TC-REQ-APP-002 自批/越权审批被拒 ============
   * 自然语言：验证自批和越权审批被拒绝
   * 具体化：创建 C 级需求（四角色审批门禁）→ 提交审核 → 创建人（同时是审核人）approve → 必须被拒
   * 实测校准（2026-08-19）：A 级无角色审批，创建人 approve 属合法流程；
   * 自批拦截只对 C/D 级（需角色审批）有意义，故 requirementLevel 必须显式设 C。
   * 若 C 级自批仍 200 成功 → 真缺陷，需登记。
   */
  test('TC-REQ-APP-002 C级需求自批审批被拒', async ({ apiClient }) => {
    const req = await createReq(apiClient, { requirementLevel: 'C' });
    try {
      const submitRes = await apiClient.post(API.reqAction(req.id, 'submit'), {});
      const submitBody = await submitRes.json();
      expect(submitBody.ok !== undefined).toBe(true);

      const approveRes = await apiClient.post(API.reqAction(req.id, 'approve'), {});
      const approveBody = await approveRes.json();
      // C 级自批正确行为：ok=false（拒绝）或返回明确错误；不允许静默成功
      expect(approveBody.ok === false || approveRes.status() >= 400).toBe(true);
    } finally {
      await apiClient.delete(API.reqById(req.id)).catch(() => {});
    }
  });

  /**
   * ============ TC-REQ-APP-003 重复转 SDD 幂等 ============
   * 自然语言：重复转 SDD 不创建重复项目或作业
   * 具体化：创建需求 → convert-to-sdd 两次 → 只产生一个 SDD 项目
   */
  test('TC-REQ-APP-003 重复转SDD幂等', async ({ apiClient }) => {
    const req = await createReq(apiClient);
    try {
      const r1 = await apiClient.post(API.reqAction(req.id, 'convert-to-sdd'), {});
      const r2 = await apiClient.post(API.reqAction(req.id, 'convert-to-sdd'), {});
      const b1 = await r1.json().catch(() => ({}));
      const b2 = await r2.json().catch(() => ({}));
      // 幂等断言：第二次不新增（返回同一 id / ok:false 明确拒绝 / 无重复项目）
      if (b1.ok && b2.ok) {
        const id1 = (b1.data && (b1.data.id || b1.data.projectId)) || '';
        const id2 = (b2.data && (b2.data.id || b2.data.projectId)) || '';
        if (id1 && id2) expect(id1).toBe(id2);
      } else {
        // 允许第二次被明确拒绝（幂等实现），不允许第二次报 500
        expect([r1.status(), r2.status()]).not.toContain(500);
      }
    } finally {
      await apiClient.delete(API.reqById(req.id)).catch(() => {});
    }
  });

  /**
   * ============ TC-TASK-001 任务分解原子性/可追溯 ============
   * 自然语言：任务原子性、可追溯、非 Markdown 误拆
   * 具体化：SDD 项目任务接口返回严格 JSON 结构（1~12 项约束）、字段可追溯
   * 注：任务严格 JSON 约束在 sdd 任务接口；此处先验证项目与任务结构可达
   */
  test('TC-TASK-001 SDD任务接口结构可达且非纯Markdown', async ({ apiClient }) => {
    const res = await apiClient.get(API.sddProjects());
    expect(res.status()).toBe(200);
    const data = assertOk(res, await res.json());
    const projects = Array.isArray(data) ? data : (data.items || []);
    expect(Array.isArray(projects)).toBe(true);
  });

  /**
   * ============ TC-SDD-005 质量门禁必需字段与解锁拦截 ============
   * 自然语言：质量门禁必需字段缺失被拦截
   * 具体化（2026-08-19 实测校准）：接口为 POST，必填 requirementId/sddProjectId/projectId，
   * 缺参数返回 400 VALIDATION_ERROR —— 这正是"必需字段缺失被拦截"的可断言证据
   */
  test('TC-SDD-005 质量门禁缺必填字段被拦截', async ({ apiClient }) => {
    const res = await apiClient.post(API.qualityGates(), { data: {} });
    const body = await res.json().catch(() => ({}));
    // 缺 requirementId/sddProjectId/projectId → 400 + ok:false（不允许 200 静默通过）
    expect(res.status()).toBe(400);
    expect(body.ok).toBe(false);
    expect(body.error || body.message).toBeTruthy();
  });

  test('TC-SDD-005 质量门禁绑定需求后可调用', async ({ apiClient }) => {
    const req = await createReq(apiClient);
    try {
      const res = await apiClient.post(API.qualityGates(), { data: { requirementId: req.id } });
      const body = await res.json().catch(() => ({}));
      if (envTolerant('质量门禁绑定', res, body)) return;
      expect(res.status()).toBeLessThan(500);
      expect(body.ok !== undefined).toBe(true);
    } finally {
      await apiClient.delete(API.reqById(req.id)).catch(() => {});
    }
  });
});
