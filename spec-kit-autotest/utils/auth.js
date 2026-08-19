/**
 * 认证工具
 * - apiLogin: 通过 API 登录获取 token
 * - uiLogin: 通过 UI 登录（供浏览器用例使用）
 */
const env = require('../config/env');
const { ApiClient } = require('./apiClient');

/**
 * API 登录（供接口测试使用）
 * @param {import('@playwright/test').APIRequestContext} request
 * @param {object} [cred] 凭据，默认使用 env 配置
 * @returns {Promise<ApiClient>}
 */
async function apiLogin(request, cred = {}) {
  const client = new ApiClient(request);
  const res = await client.post(`${env.baseURL}${env.api('/auth/login')}`, {
    data: {
      username: cred.username || env.username,
      password: cred.password || env.password,
    },
  });
  const body = await res.json();
  if (res.status() !== 200 || body.ok !== true) {
    throw new Error(`登录失败: HTTP ${res.status()}, ${JSON.stringify(body).slice(0, 200)}`);
  }
  client.setTokens(body.data.accessToken, body.data.refreshToken);
  return client;
}

/**
 * UI 登录（供浏览器 E2E 用例使用）
 * @param {import('@playwright/test').Page} page
 * @param {object} [cred]
 */
async function uiLogin(page, cred = {}) {
  await page.goto(`${env.baseURL}/login`);
  await page.waitForSelector('input[autocomplete="username"]');
  await page.fill('input[autocomplete="username"]', cred.username || env.username);
  await page.fill('input[autocomplete="current-password"]', cred.password || env.password);
  await page.click('button.auth-submit');
  // 等待跳转到登录后页面（收件箱）
  // 注意：页面存在 SSE 长连接，不能使用 networkidle，等待可见元素即可
  await page.waitForURL('**/inbox**', { timeout: env.timeout }).catch(() => {});
  await page.waitForSelector('text=收件箱', { timeout: 10000 }).catch(() => {});
}

module.exports = { apiLogin, uiLogin };
