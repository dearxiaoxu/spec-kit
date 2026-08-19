# Spec-Kit 迭代流水线（骨架）

以**测试为主**、AI 协助的开发-测试迭代门禁编排。核心思想：测试从"验货的"变成"定标准的"——SDD 产物落地时同步产出验收基线，AI 只当苦力，验收权人工死攥，专治 AI 编码同源"假绿"。

## 流水线全貌

```
需求分级 → SDD 同步基线(测试左移) → AI 编码 → 【自动门禁】→ 测试验证 → 人工审批 → 交付归档
                                                     │
                    ◄──── 根因回填（缺陷模式库扩容，越跑越准）────┘
```

## 快速开始

```bash
# 1. 查看全部门禁
python3 pipeline.py --list

# 2. 首次建立契约基线（目标站需暴露 OpenAPI）
python3 tools/fetch_contract.py --save-baseline

# 3. 演练：只做门禁初始化校验，不真正执行
python3 pipeline.py --dry-run

# 4. 跑全部门禁
python3 pipeline.py

# 5. 只跑单个门禁
python3 pipeline.py --gate contract_diff
```

退出码：`0` 全过 / `1` 有失败 / `2` 配置或用法错误 / `3` 阻断性门禁失败。

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
