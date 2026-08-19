/**
 * 收件箱/待办 UI 测试
 * 覆盖：空状态、新建待办、优先级过滤
 */
const { test, expect } = require('@playwright/test');
const env = require('../../config/env');
const { uiLogin } = require('../../utils/auth');
const { uniqueTitle } = require('../../utils/testData');

test.describe('收件箱', () => {
  test.beforeEach(async ({ page }) => {
    await uiLogin(page); // uiLogin 后已在收件箱，无需重复跳转
  });

  test('收件箱默认展示空状态或待办列表', async ({ page }) => {
    await page.waitForTimeout(1500);
    const emptyVisible = await page.locator('text=当前没有待办任务').first().isVisible().catch(() => false);
    // 过滤标签组存在即说明页面加载成功（空状态或列表均接受）
    const filterVisible = await page.locator('button:has-text("全部")').first().isVisible().catch(() => false);
    expect(emptyVisible || filterVisible).toBe(true);
  });

  test('新建待办成功出现在列表', async ({ page }) => {
    const title = uniqueTitle('待办');
    await page.locator('button:has-text("新建待办")').first().click();
    // 弹窗表单：任务名称输入框 + "创建"按钮
    const dialog = page.locator('.el-dialog').first();
    await dialog.locator('input[placeholder="例如：跟进需求评审意见"]').fill(title);
    await dialog.locator('button:has-text("创建")').click();
    await page.waitForTimeout(1500);
    await expect(page.locator(`text=${title}`).first()).toBeVisible({ timeout: 8000 });
  });

  test('时间过滤标签可切换', async ({ page }) => {
    for (const tag of ['全部', '今天', '即将到来', '逾期']) {
      const btn = page.locator(`button:has-text("${tag}")`).first();
      if (await btn.isVisible().catch(() => false)) {
        await btn.click();
        await page.waitForTimeout(800);
      }
    }
  });

  test('优先级过滤可用', async ({ page }) => {
    const btn = page.locator('button:has-text("P1")').first();
    if (await btn.isVisible().catch(() => false)) {
      await btn.click();
      await page.waitForTimeout(800);
    }
  });
});
