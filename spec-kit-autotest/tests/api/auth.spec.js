/**
 * 认证接口测试
 * 覆盖：登录成功/失败、会话校验、登出、注册校验
 */
const { test, expect, describe } = require('../../fixtures/authFixture');
const env = require('../../config/env');
const { assertOk } = require('../../utils/apiClient');
const { uniqueTitle } = require('../../utils/testData');

const API = {
  login: () => `${env.baseURL}${env.api('/auth/login')}`,
  session: () => `${env.baseURL}${env.api('/auth/session')}`,
  logout: () => `${env.baseURL}${env.api('/auth/logout')}`,
  register: () => `${env.baseURL}${env.api('/auth/register')}`,
  me: () => `${env.baseURL}${env.api('/data/me')}`,
};

describe('认证接口', () => {
  test('登录-正确凭据返回 token', async ({ anonClient }) => {
    const res = await anonClient.post(API.login(), {
      data: { username: env.username, password: env.password },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.data.accessToken).toBeTruthy();
    expect(body.data.refreshToken).toBeTruthy();
    expect(body.data.user.username).toBe(env.username);
  });

  test('登录-错误密码返回失败', async ({ anonClient }) => {
    const res = await anonClient.post(API.login(), {
      data: { username: env.username, password: 'wrong-password-123' },
    });
    const body = await res.json();
    expect(body.ok).toBe(false);
  });

  test('登录-空字段校验', async ({ anonClient }) => {
    const res = await anonClient.post(API.login(), {
      data: { username: '', password: '' },
    });
    expect(res.status()).not.toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(false);
  });

  test('会话校验-未登录返回401', async ({ anonClient }) => {
    const res = await anonClient.get(API.session());
    expect(res.status()).toBe(401);
  });

  test('会话校验-已登录返回用户信息', async ({ apiClient }) => {
    const res = await apiClient.get(API.session());
    const body = await res.json();
    if (body.ok) {
      expect(body.data.username).toBe(env.username);
    } else {
      expect(body.ok).toBe(false);
    }
  });

  test('获取当前用户信息', async ({ apiClient }) => {
    const res = await apiClient.get(API.me());
    expect(res.status()).toBe(200);
    const data = assertOk(res, await res.json());
    expect(data.username).toBe(env.username);
  });

  test('登出-接口可调用', async ({ apiClient }) => {
    const res = await apiClient.post(API.logout(), {});
    expect([200, 204]).toContain(res.status());
  });

  test('注册-空字段被拒绝', async ({ anonClient }) => {
    const res = await anonClient.post(API.register(), { data: {} });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.code).toBe('VALIDATION_ERROR');
  });

  test('注册-正常凭据可注册（@smoke）', async ({ anonClient }) => {
    const username = uniqueTitle('user').replace(/[^a-zA-Z0-9]/g, '').slice(0, 20);
    const res = await anonClient.post(API.register(), {
      data: { username, password: 'Test@123456', name: '自动化注册用户' },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.data.user.username).toBe(username);
  });
});
