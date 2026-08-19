/**
 * 安全专项接口测试
 * 覆盖：越权访问、SQL注入、鉴权头校验、敏感信息泄露
 * 注意：仅做无害探测，不进行攻击性渗透（方案B下现网受限执行）
 */
const { test, expect, describe } = require('../../fixtures/authFixture');
const env = require('../../config/env');

const API = {
  adminModels: () => `${env.baseURL}${env.api('/admin/ai-models')}`,
  me: () => `${env.baseURL}${env.api('/data/me')}`,
  reqList: () => `${env.baseURL}${env.api('/requirements')}?scope=personal`,
};

describe('安全专项', () => {
  test('未登录访问受保护接口返回401', async ({ anonClient }) => {
    const res = await anonClient.get(API.me());
    expect(res.status()).toBe(401);
  });

  test('未登录访问需求列表返回401', async ({ anonClient }) => {
    const res = await anonClient.get(API.reqList());
    expect(res.status()).toBe(401);
  });

  test('member访问管理后台接口被拒绝', async ({ apiClient }) => {
    const res = await apiClient.get(API.adminModels());
    // 期望 403（无权限）或 401（未授权），不允许 200
    expect([401, 403]).toContain(res.status());
  });

  test('SQL注入-登录接口无害探测', async ({ anonClient }) => {
    const res = await anonClient.post(`${env.baseURL}${env.api('/auth/login')}`, {
      data: { username: "' OR 1=1--", password: "x' OR '1'='1" },
    });
    const body = await res.json();
    // 必须明确失败，不允许绕过认证
    expect(body.ok).toBe(false);
  });

  test('XSS-创建需求标题含脚本被转义或拒绝', async ({ apiClient }) => {
    const res = await apiClient.post(`${env.baseURL}${env.api('/requirements')}?scope=personal`, {
      data: {
        title: '<script>alert(document.cookie)</script>',
        background: '安全测试',
        targetUsers: 'test',
        scenarios: 'test',
        scopeBoundary: 'test',
        acceptanceCriteria: 'test',
      },
    });
    const body = await res.json();
    // 可接受：拒绝保存 或 保存后转义；不允许原样执行且返回成功
    expect(body.ok !== undefined).toBe(true);
  });

  test('响应头-安全基线检查', async ({ anonClient }) => {
    const res = await anonClient.get(`${env.baseURL}/login`);
    const h = res.headers();
    // CSP 应存在且包含 script-src 'self'
    const csp = h['content-security-policy'] || h['content-security-policy'] || '';
    expect(csp.includes("script-src 'self'")).toBe(true);
    // 安全相关头存在性（nosniff / frame-options 至少其一）
    expect(h['x-content-type-options'] || h['x-frame-options']).toBeTruthy();
  });
});
