/**
 * 登录页示例：AI 写骨架 + 人工写灵魂
 * =====================================================
 * 目标：https://106.54.60.191/login（Spec-Kit 登录页）
 *
 * 本文件演示"AI 写骨架、人工写灵魂"的分工：
 *  - [AI 骨架]  常规操作：跳转、填表、点击、等待 URL——量大可交给 AI 生成
 *  - [人工灵魂] 业务断言：token 校验、错误态校验、越权校验——必须人工编写/审核
 *
 * 为什么人工必须守"灵魂"：
 *  1. AI 只会断言"没报错/跳转了"（弱断言），不会断言"token 真的写对了"
 *  2. AI 不知道业务规则（如登录失败不得写入 token），可能"改断言让测试变绿"
 *  3. 本项目页面元素 id 是动态生成的（el-id-*），定位必须用语义化方式
 * =====================================================
 */
const { test, expect } = require('@playwright/test');
const env = require('../../config/env');

/**
 * [AI 骨架] 登录页元素定位
 * 实测：登录页 input 无稳定 id（el-id-7397-* 每次刷新都变），
 *       但 Element Plus 登录表单带语义化 autocomplete 属性，据此定位最稳。
 */
const loginPage = {
  usernameInput: 'input[autocomplete="username"]',
  passwordInput: 'input[autocomplete="current-password"]',
  submitBtn: 'button.auth-submit',
  errorText: 'text=账号或密码不正确',
};

/**
 * [AI 骨架] 填写登录表单并提交（供多个用例复用）
 */
async function doLogin(page, username, password) {
  await page.fill(loginPage.usernameInput, username);
  await page.fill(loginPage.passwordInput, password);
  await page.click(loginPage.submitBtn);
}

/**
 * [人工灵魂] 读取当前会话里的 JWT 双 token
 * 实测：accessToken / refreshToken 存在 sessionStorage（不是 cookie）
 * 返回 { accessToken, refreshToken }，不存在则为空串
 */
async function getSessionTokens(page) {
  return page.evaluate(() => {
    return {
      accessToken: sessionStorage.getItem('accessToken') || '',
      refreshToken: sessionStorage.getItem('refreshToken') || '',
    };
  });
}

test.describe('登录页：AI 写骨架 + 人工写灵魂 示例', () => {
  test.beforeEach(async ({ page }) => {
    // [AI 骨架] 打开登录页
    await page.goto(`${env.baseURL}/login`);
  });

  test('① 正确登录：不仅跳转成功，还要断言双 token 真实写入（人工灵魂）', async ({ page }) => {
    // ============ [AI 骨架] 常规操作 ============
    await doLogin(page, env.username, env.password);
    await page.waitForURL('**/inbox**', { timeout: env.timeout });

    // ============ [人工灵魂] 强断言（AI 通常只写到这里的前半句）============
    // 弱断言（AI 常见写法，不够）：expect(page.url()).toContain('/inbox');
    // 强断言（人工必须补）：
    //  1. 页面真的渲染出收件箱内容（而不是白屏）
    await expect(page.locator('text=收件箱').first()).toBeVisible({ timeout: 10000 });

    //  2. sessionStorage 里双 token 真实存在、非空、且格式像 JWT（三段式）
    const { accessToken, refreshToken } = await getSessionTokens(page);
    expect(accessToken, 'accessToken 必须写入且非空').toBeTruthy();
    expect(refreshToken, 'refreshToken 必须写入且非空').toBeTruthy();
    expect(accessToken.split('.').length, 'accessToken 应为 JWT 三段式').toBe(3);
  });

  test('② 错误密码：必须断言"不写入 token"（人工灵魂，防假绿）', async ({ page }) => {
    // ============ [AI 骨架] ============
    await doLogin(page, env.username, 'wrong-password-123');

    // ============ [人工灵魂] 业务规则断言 ============
    // 规则：登录失败不得写入任何 token，否则就是安全缺陷（弱断言发现不了）
    await expect(page.locator(loginPage.errorText).first()).toBeVisible({ timeout: 8000 });
    // 仍停留在登录页（没有跳转）
    expect(page.url()).toContain('/login');

    // 关键：即使错误提示出现，也要确认 sessionStorage 里没有 token
    const { accessToken, refreshToken } = await getSessionTokens(page);
    expect(accessToken, '登录失败时不得写入 accessToken').toBeFalsy();
    expect(refreshToken, '登录失败时不得写入 refreshToken').toBeFalsy();
  });

  test('③ 空字段提交：前端校验拦截，且不产生 token（人工灵魂）', async ({ page }) => {
    // [AI 骨架] 直接点登录（不填任何内容）
    await page.click(loginPage.submitBtn);

    // [人工灵魂] 前端校验提示可见（el-form-item__error 或消息条）
    const err = page.locator('.el-form-item__error, .el-message').first();
    await expect(err).toBeVisible({ timeout: 5000 });

    // 未登录态：无 token
    const { accessToken } = await getSessionTokens(page);
    expect(accessToken).toBeFalsy();
  });

  test('④ 未登录访问受保护页：应被重定向回登录页（人工灵魂，越权基线）', async ({ page }) => {
    // [AI 骨架] 直接访问受保护页面（收件箱）
    await page.goto(`${env.baseURL}/inbox`);

    // [人工灵魂] 越权基线断言：
    //  未登录访问 /inbox 应跳回 /login（而不是直接放行或报错白屏）
    //  注意：等待可见元素，不要用 networkidle（页面有 SSE 长连接会超时）
    await page.waitForURL('**/login**', { timeout: env.timeout }).catch(() => {});
    const url = page.url();
    expect(url, `未登录访问受保护页应回到登录页，实际: ${url}`).toContain('/login');
  });

  test('⑤ 会话保持：登录后刷新页面仍保持登录态（人工灵魂，JWT 校验）', async ({ page }) => {
    // [AI 骨架] 登录
    await doLogin(page, env.username, env.password);
    await page.waitForURL('**/inbox**', { timeout: env.timeout });

    // [人工灵魂] 刷新页面（模拟用户 F5），JWT 会话应保持
    await page.reload();
    // 刷新后仍在收件箱（而不是被踢回登录页）
    await expect(page.locator('text=收件箱').first()).toBeVisible({ timeout: 10000 });
    expect(page.url()).toContain('/inbox');
  });
});
