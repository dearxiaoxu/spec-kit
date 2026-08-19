# Spec-Kit 自动化测试框架

基于 **Playwright** 的 Spec-Kit 平台自动化测试框架，同时支持**接口测试（API）**与**浏览器 E2E 测试（UI）**。

## 功能特性

- ✅ 忽略自签名证书（`ignoreHTTPSErrors`），适配当前环境
- ✅ JWT 双 token 认证封装（accessToken + refreshToken）
- ✅ 全局预登录 + 认证状态复用（加速 UI 测试）
- ✅ 接口/UI 双测试项目（`api` / `ui-chromium` / `ui-firefox`）
- ✅ 测试数据生成器（自动加时间戳，避免数据冲突）
- ✅ HTML/JSON 双格式测试报告
- ✅ 安全专项用例（越权/注入/响应头基线，均为无害探测）
- ✅ AI 用例开关（`RUN_AI_TESTS`，避免误触发模型费用）

## 目录结构

```
spec-kit-autotest/
├── config/
│   └── env.js                 # 环境配置加载（读取 .env）
├── fixtures/
│   └── authFixture.js         # Playwright fixtures（apiClient/authPage）
├── utils/
│   ├── apiClient.js           # REST 客户端封装（含 token 管理）
│   ├── auth.js                # 登录工具（API 登录 / UI 登录）
│   └── testData.js            # 测试数据生成器
├── tests/
│   ├── api/                   # 接口测试
│   │   ├── auth.spec.js       #   认证接口
│   │   ├── requirements.spec.js # 需求接口
│   │   ├── sdd.spec.js        #   SDD 接口
│   │   └── security.spec.js   #   安全专项
│   └── ui/                    # UI 测试
│       ├── login.spec.js      #   登录页
│       ├── inbox.spec.js      #   收件箱
│       └── requirements.spec.js # 需求管理
├── global-setup.js            # 全局前置（环境可达性 + 预登录）
├── playwright.config.js       # Playwright 配置
├── .env.example               # 环境变量模板
└── package.json
```

## 快速开始

### 1. 安装依赖

```bash
cd spec-kit-autotest
npm install
npx playwright install chromium   # 安装浏览器（首次）
```

### 2. 配置环境

```bash
cp .env.example .env
# 编辑 .env，填入测试环境地址与账号
```

### 3. 运行测试

```bash
npm test                 # 全部测试
npm run test:api         # 仅接口测试
npm run test:ui          # 仅 UI 测试
npm run test:smoke       # 冒烟用例（@smoke 标记）
npm run test:headed      # 有头模式运行（观察浏览器）
npm run report           # 打开 HTML 报告
```

### 4. 生成报告

运行后报告输出到 `reports/` 目录：
- `reports/html/` — HTML 报告
- `reports/test-results.json` — JSON 结果

## 环境变量说明

| 变量 | 说明 | 默认 |
|---|---|---|
| `BASE_URL` | 目标环境地址 | `https://106.54.60.191` |
| `USERNAME` | member 测试账号 | `Xuhp` |
| `PASSWORD` | 测试账号密码 | 无（必填） |
| `ADMIN_USERNAME/PASSWORD` | admin 账号 | 无 |
| `IGNORE_HTTPS_ERRORS` | 忽略证书 | `true` |
| `TIMEOUT` | 全局超时(ms) | `30000` |
| `RUN_AI_TESTS` | 是否执行 AI 用例 | `false` |

## 与测试方案的对应关系

| 测试类型 | 框架实现 | 对应方案章节 |
|---|---|---|
| 接口测试 | `tests/api/*` | 5.1 接口测试 / 7.3 用例设计 |
| UI 自动化 | `tests/ui/*` | 5.1 自动化回归测试 |
| 安全专项 | `tests/api/security.spec.js` | 附录 B 安全重点核查项 |
| 兼容性 | `ui-firefox` 项目 + 多浏览器 | 5.1 兼容性测试 |
| 性能测试 | 需结合 JMeter/k6（见方案附录 C） | 5.1 性能测试 |

## 扩展指南

### 新增接口测试

在 `tests/api/` 下新建 `xxx.spec.js`：

```js
const { test, expect, describe } = require('../../fixtures/authFixture');
const env = require('../../config/env');

describe('新模块接口', () => {
  test('示例用例', async ({ apiClient }) => {
    const res = await apiClient.get(`${env.baseURL}${env.api('/data/projects')}?scope=personal`);
    expect(res.status()).toBe(200);
  });
});
```

### 新增 UI 测试

在 `tests/ui/` 下新建 `xxx.spec.js`，使用 `uiLogin` 预登录：

```js
const { test, expect } = require('@playwright/test');
const { uiLogin } = require('../../utils/auth');

test.describe('新模块', () => {
  test.beforeEach(async ({ page }) => {
    await uiLogin(page);
    await page.goto(`${process.env.BASE_URL}/xxx`);
  });
  test('用例', async ({ page }) => {
    // ...
  });
});
```

### 元素选择器说明

当前 UI 用例中的选择器基于 Element Plus 常见结构编写，若页面结构调整导致定位失败，需按实际 DOM 更新选择器（建议使用 `data-testid` 或语义化 class）。

## 注意事项

1. **方案B（现网）限制**：现网执行时只跑只读/低风险用例，破坏性用例（删除、批量创建）仅在方案A（独立测试环境）执行。
2. **AI 用例**：`RUN_AI_TESTS=true` 会调用真实模型产生费用，默认关闭。
3. **自签名证书**：`IGNORE_HTTPS_ERRORS` 默认开启，如目标环境为正式证书可关闭。
4. **测试数据**：所有创建的数据带 `[测试]` 前缀 + 时间戳，便于识别与清理。
5. **串行执行**：`playwright.config.js` 默认 `workers: 1`。并发执行接口测试可能触发服务端会话竞争（多个 worker 同时登录导致部分请求返回 HTML），需要并发时请评估后端会话策略。
6. **系统 Chrome**：配置使用系统 Chrome 路径（`/Applications/Google Chrome.app/...`），避免下载 Playwright 浏览器内核；不同系统请通过 `CHROME_PATH` 环境变量指定。
7. **SSE 长连接**：页面存在 SSE 长连接，等待页面加载时不要使用 `networkidle`（会超时），应等待可见元素。

## 验证记录（2026-08-05，环境 https://106.54.60.191）

| 测试文件 | 用例数 | 结果 |
|---|---|---|
| tests/api/auth.spec.js | 9 | ✅ 通过 |
| tests/api/requirements.spec.js | 11 | ✅ 通过 |
| tests/api/sdd.spec.js | 7 | ✅ 通过 |
| tests/api/security.spec.js | 6 | ✅ 通过 |
| tests/ui/login.spec.js | 4 | ✅ 通过 |
| tests/ui/inbox.spec.js | 4 | ✅ 通过 |
| tests/ui/requirements.spec.js | 3 | ✅ 通过 |
| **合计** | **44** | **全部通过** |

> 说明：以上用例均为低风险只读/可逆操作，可在现网（方案B）安全执行。AI 类用例默认关闭。
