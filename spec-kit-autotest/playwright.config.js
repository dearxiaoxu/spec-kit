/**
 * Playwright 配置
 * - 忽略自签名证书（ignoreHTTPSErrors）
 * - 全局 setup 预登录并保存认证状态
 * - 支持 API / UI 两类测试项目
 */
const { defineConfig, devices } = require('@playwright/test');
const env = require('./config/env');

module.exports = defineConfig({
  testDir: './tests',
  timeout: env.timeout,
  expect: { timeout: 10000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // 串行执行避免并发登录触发服务端会话竞争（可手动 --workers=N 调整）
  workers: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'reports/html' }],
    ['json', { outputFile: 'reports/test-results.json' }],
  ],
  use: {
    baseURL: env.baseURL,
    ignoreHTTPSErrors: env.ignoreHTTPSErrors,
    // 使用系统 Chrome，避免额外下载浏览器内核（如路径不同可修改）
    launchOptions: {
      executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    },
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    // 关闭视频录制（避免依赖 ffmpeg 下载）
    video: 'off',
  },
  // 登录预置（全局）
  globalSetup: require.resolve('./global-setup'),
  projects: [
    // 纯单元测试（不依赖目标环境，可验证工具层边界行为）
    {
      name: 'unit',
      testMatch: /tests\/unit\/.*\.spec\.js/,
    },
    // 接口测试（无需浏览器）
    {
      name: 'api',
      testMatch: /tests\/api\/.*\.spec\.js/,
      use: { ...devices['Desktop Chrome'] },
    },
    // UI 测试（Chromium）
    {
      name: 'ui-chromium',
      testMatch: /tests\/ui\/.*\.spec\.js/,
      use: { ...devices['Desktop Chrome'] },
    },
    // UI 测试（Firefox，兼容性）
    {
      name: 'ui-firefox',
      testMatch: /tests\/ui\/.*\.spec\.js/,
      use: { ...devices['Desktop Firefox'] },
    },
  ],
});
