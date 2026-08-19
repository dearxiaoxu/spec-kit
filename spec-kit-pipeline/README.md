# Spec-Kit 迭代流水线（骨架）

以**测试为主**、AI 协助的开发-测试迭代门禁编排。核心思想：测试从"验货的"变成"定标准的"——SDD 产物落地时同步产出验收基线，AI 只当苦力，验收权人工死攥，专治 AI 编码同源"假绿"。

## 流水线全貌

```
需求分级 → SDD 同步基线(测试左移) → AI 编码 → 【自动门禁】→ 测试验证 → 人工审批 → 交付归档
                                                     │
                    ◄──── 根因回填（缺陷模式库扩容，越跑越准）────┘
```

## 运行启动顺序

> 环境前提（已实测确认）：
> - **Python**：用 `/opt/homebrew/bin/python3`（3.14）；`~/.workbuddy` 下的 managed/venv python 因缺 libpython 动态库不可用
> - **Node/Playwright**：`spec-kit-autotest` 内 node_modules 已装，`npm run test:*` 可用
> - **凭据**：`spec-kit-autotest/.env` 已有有效账号（已实测能登录拿 token）；凭据不入库、不打印

### A. 首次初始化（一次性）

```bash
cd /Users/xiaoxu/Desktop/spec-kit/spec-kit-pipeline

# 1. 演练：确认门禁能初始化（不真跑）
/opt/homebrew/bin/python3 pipeline.py --dry-run

# 2.（可选）建立契约基线：自动登录 + 拉 OpenAPI
#    ⚠️ 2026-08-19 实测：目标站未暴露 OpenAPI（/api/v1/openapi.json 404），
#      此步当前会失败，contract_diff 保持跳过；待后端提供文档后再执行
/opt/homebrew/bin/python3 tools/fetch_contract.py --auto-login --save-baseline
```

### B. 日常迭代（每次开发/测试迭代跑一次）

```bash
cd /Users/xiaoxu/Desktop/spec-kit/spec-kit-pipeline

# 1. 跑全部门禁（推荐）：
#    static_scan → pattern_regression → e2e_regression(test:api) → mutation_check
/opt/homebrew/bin/python3 pipeline.py

# 2. 快速回归（接口测试全量耗时较长时，用 smoke 标签先冒烟）
/opt/homebrew/bin/python3 pipeline.py --script test:smoke

# 3. 查看报告（JSON + Markdown，失败项人可读）
open report/$(ls -t report/ | grep .md$ | head -1)
```

### C. 专项操作

```bash
# 只跑单个门禁
/opt/homebrew/bin/python3 pipeline.py --gate static_scan
/opt/homebrew/bin/python3 pipeline.py --gate pattern_regression

# 单独跑 Playwright（不进流水线，直接调试）
cd /Users/xiaoxu/Desktop/spec-kit/spec-kit-autotest
npm run test:smoke    # 冒烟（@smoke 标签）
npm run test:api      # 接口全量
npm run test:ui       # UI 全量（Chromium + Firefox）
npm run report        # 打开 Playwright HTML 报告

# 进入流水线前预跑一次契约拉取（后端提供文档后）
/opt/homebrew/bin/python3 pipeline.py --fetch-contract --auto-login
```

### 退出码

`0` 全过 / `1` 有失败 / `2` 配置或用法错误 / `3` 阻断性门禁失败（流水线中断）。

### 各门禁当前状态（2026-08-19 实测）

| 门禁 | 启动顺序中的位置 | 状态 |
|---|---|---|
| `contract_diff` | 全量第 1 个 | ⏸ 跳过（无 OpenAPI 基线；后端未暴露文档） |
| `static_scan` | 全量第 2 个 | ✅ error 0 / warn 3（测试密码告警） |
| `pattern_regression` | 全量第 3 个 | ✅ 10/10（真实探测目标站） |
| `e2e_regression` | 全量第 4 个 | ✅ test:unit 9/9；默认跑 test:api |
| `mutation_check` | 全量第 5 个 | ⏸ 跳过（未配 Stryker） |

## 门禁清单

| 门禁 | 类型 | 作用 | 骨架状态 |
|---|---|---|---|
| `contract_diff` | blocking | OpenAPI 契约 diff，破坏性变更阻断准入 | 可用（需先 fetch 基线） |
| `static_scan` | — | 异源静态扫描（内置敏感信息正则 + 可接 Semgrep/SonarQube） | 可用 |
| `pattern_regression` | blocking | AI 缺陷模式库回归（10 类，只读探测） | 可用（已关联 580 用例，实测 + 负向验证） |
| `e2e_regression` | — | 调用 Playwright `test:api` 并解析通过率 | 可用（需 Playwright 项目） |
| `mutation_check` | — | 变异测试验证断言有效性（防同源假绿） | 占位（配置 `mutation_cmd` 后启用） |

## 铁律（防假绿，务必遵守）

1. **断言人工写，AI 只补盲**——自动化用例的关键断言不得由生成代码的同一模型自动生成后直接入库。
2. **门禁自动但不静默**——每次运行都产出 `report/pipeline-*.md`，失败项必须人可读。
3. **Judge 不唯一验收**——关键产物抽样由独立模型或人工复评（`assets/golden_set.json` 登记）。
4. **模式库测试维护**——`assets/patterns.json` 由测试维护，发现新集中缺陷类别即回填。
5. **凭据不入库**——账号密码走环境变量/CI Secret（对齐测试方案 §3.3），本项目不记录任何凭据。

## 目录结构

```
spec-kit-pipeline/
├── pipeline.py            # 主入口：编排 + 报告 + 退出码
├── config.json            # 配置（路径/目标站/门禁开关/外部工具命令）
├── gates/                 # 门禁模块（统一 Gate 接口，可插拔）
│   ├── base.py            # Gate 基类 + GateResult
│   ├── contract_diff.py   # 门禁1：契约 diff（blocking）
│   ├── static_scan.py     # 门禁2：异源静态扫描
│   ├── pattern_regression.py # 门禁3：AI 缺陷模式库回归（blocking）
│   ├── e2e_regression.py  # 门禁4：Playwright 回归对接
│   └── mutation_check.py  # 门禁5：变异测试（占位）
├── assets/
│   ├── patterns.json      # AI 缺陷模式库（10 类）
│   ├── golden_set.json    # AI 质量黄金集（双标注登记）
│   └── contract/          # 契约快照（snapshot=基线 / current=当前）
├── tools/
│   └── fetch_contract.py  # 拉取 OpenAPI（--save-baseline 建基线）
└── report/                # 每次运行的 JSON/Markdown 报告
```

## 阶段路线（4 周落地）

- **W1 跑通**：`e2e_regression` 挂到现有 Playwright（`npm run test:api`），每轮迭代自动回归。
- **W2 契约门禁**：fetch 基线 + `contract_diff` 接入，AI 改接口不再悄悄改。
- **W3 模式库**：从 580 条用例中 AI 同源专项 100 条沉淀进 `patterns.json`。
- **W4 防假绿**：黄金集双标注 + Stryker 变异测试（配置 `mutation_cmd`）+ 独立复评 SOP。

## 免责

骨架阶段 `contract_diff` 的 diff 为结构级比较（端点/必填字段/枚举），不覆盖 Schema 深层语义；
`pattern_regression` 的探测为只读，攻击性用例请按测试方案安全专项执行。
