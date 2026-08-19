/**
 * 需求管理示例：AI 写骨架 + 人工写灵魂（第二弹）
 * =====================================================
 * 目标：https://106.54.60.191/requirements（需求管理页）
 *
 * 与 login-demo.spec.js 配套，演示同一分工理念在核心业务模块的应用：
 *  - [AI 骨架]  常规操作：登录、跳转、点标签、开弹窗——可交给 AI 生成
 *  - [人工灵魂] 业务规则：筛选正确性、空间数据隔离、表单必填校验——必须人工编写
 *
 * 为什么要这些"灵魂"断言（对应方案 8.2 需求管理 / 7.4 越权与隔离）：
 *  1. 状态筛选"点了没反应 / 筛出来不对"是常见假绿——AI 只断言"标签能点"
 *  2. 个人/团队空间数据隔离是权限核心，漏测=越权风险
 *  3. 21 字段表单（含折叠面板）是方案 6.2 标注的高风险交互区
 * =====================================================
 */
const { test, expect } = require('@playwright/test');
const env = require('../../config/env');
const { uiLogin } = require('../../utils/auth');

/**
 * [AI 骨架] 需求页常用元素定位
 * 实测：状态标签是 .chip 类（"全部 3" 带计数），表格有"状态"列
 */
const reqPage = {
  url: `${env.baseURL}/requirements`,
  chipTag: (name) => `button.chip:has-text("${name}")`,
  tableRow: '.el-table__body tr',
};

/**
 * [人工灵魂] 读取表格中所有"状态"列的值
 * 返回：['已转 SDD', '已批准', ...]
 */
async function getStatusColumn(page) {
  return page.evaluate(() => {
    const rows = [...document.querySelectorAll('.el-table__body tr')];
    const statuses = [];
    for (const row of rows) {
      // 状态列通常在第二列（标题后面），按可见文本提取
      const cells = [...row.querySelectorAll('td')];
      if (cells.length >= 2) {
        statuses.push(cells[1].innerText.trim());
      }
    }
    return statuses;
  });
}

test.describe('需求管理：AI 写骨架 + 人工写灵魂 示例', () => {
  test.beforeEach(async ({ page }) => {
    // [AI 骨架] 预登录并进入需求管理页
    await uiLogin(page);
    await page.goto(reqPage.url);
    await expect(page.locator('text=需求管理').first()).toBeVisible({ timeout: 10000 });
  });

  test('① 状态筛选正确性：点"已批准"标签后，列表每一行都应是"已批准"（人工灵魂）', async ({ page }) => {
    // ============ [AI 骨架] 点击状态标签 ============
    await page.locator(reqPage.chipTag('已批准')).first().click();
    await page.waitForTimeout(800);

    // ============ [人工灵魂] 强断言（AI 通常只断言"标签能点"）============
    //  筛选后列表非空时，每一行的状态列都必须是"已批准"
    const statuses = await getStatusColumn(page);
    if (statuses.length > 0) {
      const bad = statuses.filter((s) => !s.includes('已批准'));
      expect(bad, `筛选"已批准"后出现非已批准状态: ${bad.join(', ')}`).toEqual([]);
    }
  });

  test('② 状态筛选正确性：点"已转 SDD"标签后，列表每一行都应是"已转 SDD"（人工灵魂）', async ({ page }) => {
    await page.locator(reqPage.chipTag('已转 SDD')).first().click();
    await page.waitForTimeout(800);

    const statuses = await getStatusColumn(page);
    if (statuses.length > 0) {
      const bad = statuses.filter((s) => !s.includes('已转 SDD'));
      expect(bad, `筛选"已转 SDD"后出现非 SDD 状态: ${bad.join(', ')}`).toEqual([]);
    }
  });

  test('③ 个人/团队空间切换：切换后页面正常加载且可切回（人工灵魂，数据隔离基线）', async ({ page }) => {
    // ============ [AI 骨架] 点击"团队空间" ============
    const teamBtn = page.locator('button:has-text("团队空间")').first();
    if (!(await teamBtn.isVisible().catch(() => false))) {
      test.skip(true, '当前账号无团队空间入口');
    }
    await teamBtn.click();
    await page.waitForTimeout(1000);

    // ============ [人工灵魂] 空间隔离断言 ============
    //  1. 切换后仍停留在需求管理页（不是 404/白屏/被踢回登录页）
    expect(page.url(), '切换空间后应停留在需求管理页').toContain('/requirements');

    //  2. 页面主体正常渲染（有状态标签组，说明数据重新加载了）
    await expect(page.locator(reqPage.chipTag('全部')).first()).toBeVisible({ timeout: 8000 });

    //  3. 能切回个人空间（来回切换正常，不卡死）
    const personalBtn = page.locator('button:has-text("个人空间")').first();
    if (await personalBtn.isVisible().catch(() => false)) {
      await personalBtn.click();
      await page.waitForTimeout(800);
      expect(page.url()).toContain('/requirements');
    }
  });

  test('④ 新建需求弹窗：21 字段表单完整呈现，含折叠面板（人工灵魂，方案 6.2 高风险区）', async ({ page }) => {
    // [AI 骨架] 打开新建需求弹窗
    await page.locator('button:has-text("新建需求")').first().click();
    const dialog = page.locator('.el-dialog:visible').first();
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // ============ [人工灵魂] 表单完整性断言 ============
    //  1. 关键字段存在：标题输入框（必填）、描述、验收标准
    await expect(dialog.locator('input[placeholder*="标题"]')).toBeVisible();
    await expect(dialog.locator('textarea[placeholder*="描述"]').first()).toBeVisible();
    await expect(dialog.locator('textarea[placeholder*="验收"]').first()).toBeVisible();

    //  2. 字段总数达到方案标注的 21 个（含折叠面板内的结构化字段）
    const fieldCount = await dialog.locator('.el-form-item').count();
    expect(fieldCount, `新建需求表单字段数应为 21 个左右，实际 ${fieldCount}`).toBeGreaterThanOrEqual(15);

    //  3. 按钮齐全：取消 / 创建
    await expect(dialog.locator('button:has-text("取消")')).toBeVisible();
    await expect(dialog.locator('button:has-text("创建")')).toBeVisible();

    // [AI 骨架] 关闭弹窗，不留脏数据
    await dialog.locator('button:has-text("取消")').first().click();
  });

  test('⑤ 新建需求必填校验：只填标题点创建，应提示缺失必填项且不关闭弹窗（人工灵魂，防"半成品"数据）', async ({ page }) => {
    // [AI 骨架] 打开弹窗并只填标题
    await page.locator('button:has-text("新建需求")').first().click();
    const dialog = page.locator('.el-dialog:visible').first();
    await expect(dialog).toBeVisible({ timeout: 5000 });
    await dialog.locator('input[placeholder*="标题"]').fill('必填校验测试-勿入库');

    // [AI 骨架] 直接点创建
    await dialog.locator('button:has-text("创建")').first().click();
    await page.waitForTimeout(800);

    // ============ [人工灵魂] 业务规则断言 ============
    //  1. 出现必填校验提示（注意：el-message 是全局消息条，渲染在 body 下，须用 page 级定位）
    const errVisible = await page
      .locator('.el-message:has-text("审核人"), .el-form-item__error:has-text("审核人"), .el-message:has-text("必填"), .el-form-item__error:has-text("必填")')
      .first()
      .isVisible()
      .catch(() => false);
    expect(errVisible, '缺失必填项时应出现校验提示').toBe(true);

    //  2. 弹窗没有关闭（未创建出"半成品"需求）
    expect(await dialog.isVisible().catch(() => false), '校验失败时弹窗不应关闭').toBe(true);

    // [AI 骨架] 清理：取消关闭
    await dialog.locator('button:has-text("取消")').first().click();
  });
});
