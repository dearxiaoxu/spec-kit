/**
 * 登录页 UI 测试
 * 覆盖：正确登录、错误密码、空字段校验、会话保持
 */
const { test, expect } = require('@playwright/test');
const env = require('../../config/env');

test.describe('登录页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${env.baseURL}/login`);
  });

  test('正确凭据登录成功跳转收件箱（@smoke）', async ({ page }) => {
    await page.fill('input[autocomplete="username"]', env.username);
    await page.fill('input[autocomplete="current-password"]', env.password);
    await page.click('button.auth-submit');

    await page.waitForURL('**/inbox**', { timeout: env.timeout });
    // 登录后应看到侧边栏与页面主体
    await expect(page.locator('text=收件箱').first()).toBeVisible({ timeout: 10000 });
  });

  test('错误密码提示失败且不跳转', async ({ page }) => {
    await page.fill('input[autocomplete="username"]', env.username);
    await page.fill('input[autocomplete="current-password"]', 'wrong-password');
    await page.click('button.auth-submit');

    // 出现"账号或密码不正确"错误提示
    await expect(page.locator('text=账号或密码不正确').first()).toBeVisible({ timeout: 8000 });
    // 停留在登录页
    expect(page.url()).toContain('/login');
  });

  test('空字段提交被前端校验拦截', async ({ page }) => {
    await page.click('button.auth-submit');
    // 前端校验提示（el-form-item__error 或消息条）
    const err = page.locator('.el-form-item__error, .el-message').first();
    await expect(err).toBeVisible({ timeout: 5000 });
  });

  test('登录成功后可访问受保护页面', async ({ page }) => {
    await page.fill('input[autocomplete="username"]', env.username);
    await page.fill('input[autocomplete="current-password"]', env.password);
    await page.click('button.auth-submit');
    await page.waitForURL('**/inbox**', { timeout: env.timeout });

    await page.goto(`${env.baseURL}/dashboard`);
    await expect(page.locator('text=仪表盘').first()).toBeVisible({ timeout: 10000 });
  });
});
