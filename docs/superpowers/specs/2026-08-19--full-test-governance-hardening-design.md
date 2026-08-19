# Spec-Kit 测试治理全面加固设计

## 1. 背景与目标

当前项目已经具备 Python 门禁编排、Playwright API/UI 回归、测试文档与执行资产，但仍存在环境异常被容错为通过、现网与有状态测试混跑、认证伪刷新、清理失败静默、阶段参数不生效、绝对路径绑定、契约与变异门禁长期跳过、报告与真实测试规模漂移等问题。

本次目标是把现有骨架升级为可解释、可迁移、可用于准出的测试治理链路。所有结果必须区分业务失败、阻断失败、合法跳过、环境异常和配置错误；任何危险测试必须通过环境和显式开关双重授权。

## 2. 统一状态模型

新增权威状态枚举：

- `PASS`：真实执行并通过。
- `FAIL`：业务断言失败。
- `BLOCKED`：阻断门禁失败。
- `SKIP`：策略允许的合法跳过。
- `FLAKY`：重试后通过或结果波动。
- `ENV_ERROR`：503、HTML 响应、网络不可达或环境异常超阈值。
- `CONFIG_ERROR`：配置、依赖、路径或必需门禁缺失。

`GateResult` 保留 `passed`、`skipped`、`blocking` 兼容字段，但由 `status` 派生；报告、汇总与退出码只以 `status` 为准，禁止各 Gate 自由拼接矛盾布尔组合。

退出码：`0` 允许准出，`1` 普通失败或波动超阈值，`2` 配置错误，`3` 阻断失败，`4` 环境不可用。

## 3. 现网安全与测试分层

环境分为 `production-like`、`isolated`、`local`。

Playwright 脚本拆分为：

- `test:api:readonly`：查询、鉴权、结构和无害负向验证。
- `test:api:stateful`：创建、更新、审批、归档等可逆操作。
- `test:api:ai`：真实模型调用。
- `test:api:destructive`：删除、批量操作和破坏性安全验证。
- `test:api`：按照环境组合允许的安全子集。
- `test:ci`：单元测试、静态检查和 readonly。

保护规则：

- `production-like` 默认只允许 readonly。
- stateful 需要 `ALLOW_STATEFUL_TESTS=true`。
- AI 需要 `RUN_AI_TESTS=true`。
- destructive 同时需要 `TEST_ENV_TYPE=isolated` 和 `ALLOW_DESTRUCTIVE_TESTS=true`。
- 未满足授权时返回 `CONFIG_ERROR`，不伪装成通过。
- 日志只输出开关状态，不输出凭据。

## 4. 环境异常与波动

废弃 `envTolerant()` 静默 `return` 的通过语义，替换为只负责分类的 `classifyEnvironmentFailure()`。环境异常必须体现在 Playwright annotation、附件或结构化报告中。

- 单条 503、HTML 或网络异常标记 `ENV_ERROR`。
- 同轮环境异常超过配置阈值时，E2E Gate 整体返回 `ENV_ERROR`。
- P0 鉴权、数据隔离、审批、幂等测试不得豁免。
- retry 后通过的测试计为 `FLAKY`，不计稳定通过。

## 5. 认证策略

删除 `ApiClient` 中没有后端契约支撑的伪刷新能力。收到 401 时直接返回响应，不重试旧 Token。每条 fixture 在建立客户端时重新登录；登录失败必须明确失败。

只有后端提供真实 refresh 接口及请求响应契约后，才重新引入刷新逻辑。

## 6. 资源生命周期

新增 `ResourceTracker`：测试创建资源后登记类型、ID、标题和清理函数；`afterEach`/`afterAll` 逆序清理。

- 禁止裸 `.catch(() => {})`。
- 清理 404 视为幂等成功。
- 401、403、5xx 和网络失败记录为 cleanup failure。
- 清理失败不得覆盖原始断言失败。
- 原测试通过但关键清理失败时，产生 teardown failure 或 `ENV_ERROR`。
- 报告列出残留资源 ID，支持人工补偿清理。

## 7. 阶段化门禁

实现有效的 `--stage`：

- `code`：unit、static scan。
- `smoke`：pattern regression、readonly smoke。
- `test`：unit、readonly、stateful、UI。
- `release`：contract、全量安全回归、mutation。
- `ai`：AI 专项。
- `destructive`：隔离环境破坏性专项。

每个 Gate 配置增加 `required`、`skip_policy` 和 `stages`。`skip_policy` 支持 `allow`、`warn`、`fail`；`fail` 将无法执行的必需门禁映射为 `CONFIG_ERROR`。

## 8. 配置与路径

配置路径改为相对 `config.json` 解析，环境变量可覆盖关键项。启动时校验解析路径存在且落在允许的项目范围内。

默认结构：

```json
{
  "environment": "production-like",
  "project_root": ".",
  "autotest_dir": "../spec-kit-autotest",
  "report_dir": "report"
}
```

输出解析路径和功能开关，但所有密码、Token、Authorization、Secret 必须脱敏。

## 9. 契约门禁

优先使用后端 OpenAPI。目标站未提供 OpenAPI 时，使用仓库内人工审核的关键接口 JSON Schema 基线，至少覆盖登录双 Token、需求状态、SDD 项目与任务、质量门禁、审批转换及 job/SSE 状态。

release 阶段如果 OpenAPI 与 Schema 基线均不存在，返回 `CONFIG_ERROR`，不得长期合法跳过。

## 10. 扫描与变异测试

静态质量链包括内置凭据扫描、ESLint、固定版本与规则集的 Semgrep、敏感文件检查。外部工具非零退出必须映射为 `FAIL` 或 `CONFIG_ERROR`，真实密钥立即阻断。

变异测试先覆盖纯逻辑工具模块，不直接变异依赖现网的 E2E。使用固定 Stryker 配置和阈值；release 阶段工具缺失或分数不足分别映射为 `CONFIG_ERROR` 或 `FAIL`。

## 11. 报告

报告新增：`run_id`、Git commit、environment、stage、起止时间、duration、权威 status、executed/passed/failed/skipped/flaky/env_error、cleanup failures、危险开关状态和 Gate 诊断指标。

README 不再手写当前测试数量和“全部通过”。测试规模从 Playwright list/report 自动生成；验证记录必须绑定日期、commit、环境和实际状态数量，旧 44 条记录标记为历史快照。

## 12. 测试与验收

流水线单测覆盖七种状态、退出码 0/1/2/3/4、异常映射、stage、skip policy、路径边界、报告缺失/损坏/超时、外部工具缺失、环境阈值、清理残留和脱敏。

验收条件：

1. Python 与 Node 单元测试通过。
2. production-like 下危险脚本被拒绝。
3. isolated 加显式开关后危险脚本才可启动。
4. dry-run 不访问现网。
5. readonly 可独立执行。
6. 报告不存在假 PASS、静默环境错误或隐藏清理失败。
7. ESLint、Semgrep、Stryker 配置可验证；外部工具不可用时如实报告。
8. 不执行真实 AI 请求，不未经授权运行现网有状态或破坏性测试。

## 13. 实施分期

### 阶段一：可信状态与安全隔离

状态枚举、退出码、环境分类、伪刷新删除、测试脚本分层、危险开关和资源追踪。

### 阶段二：门禁与配置工程化

stage、skip policy、相对路径、报告增强、Schema 契约兜底。

### 阶段三：质量工具与资产同步

完整自测、ESLint/Semgrep/Stryker、测试清单自动生成、README 和执行说明同步。

每阶段独立验证；不得用后续阶段的未完成能力掩盖当前阶段失败。

## 14. 非目标与限制

- 不猜测或模拟不存在的 Token refresh 接口。
- 不在本次实施中调用真实 AI。
- 不在 production-like 环境执行 stateful/destructive 测试。
- 不声称未执行的 Semgrep、Stryker 或现网回归已经通过。
- 外部依赖无法安装或目标站不稳定时，保留可运行配置并如实标记验证状态。
