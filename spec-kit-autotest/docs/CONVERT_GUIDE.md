# 自然语言测试用例 → 自动化代码 转换指南

> 目标：把 `Spec-Kit平台580条测试用例-v3.0.xlsx` 里的自然语言用例（TC-XXX）逐步转换为可自动执行的 Playwright 代码。
> 参考实现：`tests/api/converted_demo.spec.js`（7 条用例全部实测通过，2026-08-19）。

## 为什么不能直接"AI 翻译"

580 条用例的「测试步骤/预期结果」是**模板化泛化描述**（"进入X定位Y、按测试数据执行正常/异常/边界操作、核对页面反馈/接口响应/审计记录"），
它只告诉你**测什么功能点**，没告诉你**具体怎么操作、断言什么**。

直接让 AI 照抄转换，AI 只能"脑补"具体步骤 → 生成的都是猜的，且可能把错误行为当正确行为（这正是 AI 编码同源"假绿"风险）。
因此转换必须走下面的三步法，**断言必须人工把关**。

## 三步转换法

### 第 1 步：去泛化（最重的一步，人工主导）
把泛化描述扩写成【具体操作 + 具体预期】：
- 从用例标题 + 模块知识 + 接口清单推导具体场景（正常/异常/边界）
- 从 580 用例的字段（测试数据/优先级/执行阶段）反推要覆盖的分支
- **对照已有自动化代码**：看同类接口已怎么调用（避免字段依赖踩坑），不要凭空造

### 第 2 步：映射
| 自然语言 | → | 代码 |
|---|---|---|
| 前置条件：已登录 | → | `fixtures/authFixture` 的 `{ apiClient }`（已登录客户端） |
| 未登录场景 | → | `{ anonClient }`（匿名客户端，测 401） |
| 具体操作 | → | `apiClient.get/post/put/delete(url, { data })` |
| 接口路径 | → | `env.baseURL + env.api('/xxx')`（集中 API 常量） |
| 测试数据 | → | `utils/testData` 的生成器（`requirementData` 等）+ overrides |
| 具体预期 | → | `expect(...)`（状态码 / `assertOk` / 结构断言） |
| 清理 | → | 写操作用例结束 `delete` 清理（方案B受控规范） |

### 第 3 步：断言人工校验（防同源铁律）
- 关键断言（状态机/鉴权/审批/安全）**人工背靠背评审**，AI 只辅助补充
- AI 输出非确定性的场景（Prompt 注入、AI 生成）用**结构断言**：只验 `ok/status/结构`，不精确匹配内容
- 生成代码必须能 `npx playwright test` 跑通才入库

## 项目速查（Spec-Kit autotest）

- **fixture**：`fixtures/authFixture.js` → `apiClient`（已登录）/ `anonClient`（匿名）/ `authPage`（UI）
- **工具**：`utils/apiClient.js`（自动刷新 token、`assertOk`）、`utils/auth.js`（apiLogin/uiLogin）、`utils/testData.js`（requirementData 等）
- **接口路径**：统一 `env.baseURL + env.api('/requirements')` 模式；端点清单见测试方案 §2.2.2
- **已知字段依赖坑**：
  - 创建需求 `reviewerId` 必须取当前用户 id（先 `GET /data/me`），空值返回 400
  - 需求字段：title / background / targetUsers / scenarios / scopeBoundary / acceptanceCriteria / boundaryConditions
  - 会话创建返回 `conv.id`（或 `_id`），消息接口 `/conversations/{id}/messages`
- **安全用例（方案B现网）**：只做无害探测（401/403 断言、注入串明确失败），攻击性验证留方案A隔离环境
- **AI 用例**：默认 `RUN_AI_TESTS=false` 跳过真模型调用（省费用），需要时在 .env 开启

## 转换清单管理

每转一批用例更新 `patterns.json` 的 `test_cases` 映射（pattern_regression 门禁会随回归自动跑新用例）。
建议按模块批次推进：先转 P0/T0（认证、需求管理、安全），再 P1，最后 P2。
