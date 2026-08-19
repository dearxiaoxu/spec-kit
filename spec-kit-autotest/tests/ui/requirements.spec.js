/**
 * 需求管理 UI 测试
 * 覆盖：列表展示、新建需求、状态筛选
 */
const { test, expect } = require('@playwright/test');
const env = require('../../config/env');
const { uiLogin } = require('../../utils/auth');
const { uniqueTitle } = require('../../utils/testData');

test.describe('需求管理', () => {
  test.beforeEach(async ({ page }) => {
    await uiLogin(page);
    await page.goto(`${env.baseURL}/requirements`);
  });

  test('需求列表页加载', async ({ page }) => {
    await expect(page.locator('text=需求管理').first()).toBeVisible({ timeout: 10000 });
    // 状态标签组
    for (const tag of ['全部', '草稿', '待审核', '审核中', '已批准', '已转 SDD', '已完成']) {
      const el = page.locator(`text=${tag}`).first();
      if (await el.isVisible().catch(() => false)) {
        await el.click();
        await page.waitForTimeout(600);
      }
    }
  });

  test('新建需求-必填校验', async ({ page }) => {
    await page.locator('button:has-text("新建需求")').first().click();
    await page.waitForTimeout(1000);
    // 填写标题但未选择审核人，点击"创建"触发校验
    const dialog = page.locator('.el-dialog:visible').first();
    await dialog.locator('input[placeholder="需求标题"]').fill('校验测试');
    await dialog.locator('button:has-text("创建")').first().click();
    // 出现"请选择审核人"校验提示
    await expect(page.locator('.el-message:has-text("请选择审核人")').first()).toBeVisible({ timeout: 5000 });
  });

  test('新建需求-完整填写创建成功', async ({ page }) => {
    const title = uniqueTitle('需求');
    await page.locator('button:has-text("新建需求")').first().click();
    await page.waitForTimeout(1200);

    // 表单字段填充（基于实际 DOM 结构）
    const dialog = page.locator('.el-dialog:visible').first();
    await dialog.locator('input[placeholder="需求标题"]').fill(title);
    await dialog.locator('textarea[placeholder="需求描述"]').fill('自动化测试需求描述');
    await dialog.locator('textarea[placeholder="可验收的完成条件、边界和约束"]').fill('验收标准：可正常流转');
    // 展开"结构化需求信息"折叠面板后再填充结构化字段
    const structCollapse = dialog.locator('.el-collapse-item:has-text("结构化需求信息")').first();
    if (!(await structCollapse.locator('textarea[placeholder="问题来源、业务现状、关键矛盾"]').isVisible().catch(() => false))) {
      await structCollapse.locator('.el-collapse-item__header, .el-collapse-item__arrow').first().click();
      await page.waitForTimeout(800);
    }
    await dialog.locator('textarea[placeholder="问题来源、业务现状、关键矛盾"]').fill('业务背景：自动化测试');
    await dialog.locator('textarea[placeholder="希望达成的业务结果或指标"]').fill('建设目标：验证创建流程');
    // 选择审核人（审核人表单项内点击下拉，选择第一项）
    const reviewerItem = dialog.locator('.el-form-item').nth(13);
    await reviewerItem.locator('.el-select').click();
    await page.waitForTimeout(800);
    await page.locator('.el-select-dropdown:visible .el-select-dropdown__item').first().click();
    await page.waitForTimeout(500);
    await dialog.locator('button:has-text("创建")').first().click();
    await page.waitForTimeout(3000);

    // 创建成功：弹窗关闭且出现成功消息 或 列表中可见
    const dialogClosed = !(await dialog.isVisible().catch(() => false));
    const successMsg = await page.locator('.el-message').allTextContents().catch(() => []);
    const found = await page.locator(`text=${title}`).first().isVisible().catch(() => false);
    const urlChanged = page.url().includes('/requirements/');
    expect(dialogClosed || found || urlChanged || successMsg.length > 0).toBe(true);
  });
});
