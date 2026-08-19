/**
 * Playwright fixtures
 * - apiClient: 已登录的 API 客户端（供接口测试使用）
 * - authPage: 已登录的浏览器页面（供 UI 测试使用）
 */
const { test: base } = require('@playwright/test');
const { apiLogin } = require('../utils/auth');
const { ApiClient } = require('../utils/apiClient');
const env = require('../config/env');

exports.test = base.extend({
  /** 已登录 API 客户端 */
  apiClient: async ({ request }, use) => {
    const client = await apiLogin(request);
    await use(client);
  },

  /** 匿名 API 客户端（未登录，测试鉴权场景） */
  anonClient: async ({ request }, use) => {
    await use(new ApiClient(request));
  },

  /** 已登录页面（UI 测试用） */
  authPage: async ({ page }, use) => {
    const { uiLogin } = require('../utils/auth');
    await uiLogin(page);
    await use(page);
  },
});

// 导出 test 和 expect
exports.expect = base.expect;
exports.describe = base.describe;
