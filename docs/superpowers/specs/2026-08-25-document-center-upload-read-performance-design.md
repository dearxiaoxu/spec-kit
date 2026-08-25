# 文档中心上传、读取与性能测试设计

## 1. 目标与范围

为 Spec-Kit 文档中心建立可重复、可清理、具备业务断言的自动化测试，覆盖：

- 单文档上传、列表查询、内容读取和删除闭环。
- 多种文件格式的上传与读取兼容性。
- 10 份 1MB 文档的受控并发上传、读取性能和响应时间。
- 未认证、无效 ID、空文件、伪造扩展名等失败路径。
- 文档中心 UI 的上传、列表卡片和预览冒烟流程。

不引入 k6、Artillery 或新的运行时依赖。性能结果是当前授权隔离环境下的受控基线，不等同于容量压测结论。

## 2. 已确认接口

- `POST /api/v1/docs/upload`：`multipart/form-data`，支持 `file`、`docType`、`scope`、`teamId`、`projectId`。
- `GET /api/v1/docs/list`：查询文档列表。
- `GET /api/v1/docs/view?id=<id>`：读取文档内容。
- `POST /api/v1/docs/archive`：归档文档。
- `POST /api/v1/docs/delete`：删除文档。

测试以 API 为主要验证面，UI 只验证关键用户路径。接口性能不得混入浏览器渲染、动画或文件选择器耗时。

## 3. 测试数据与格式矩阵

### 3.1 文本类

- Markdown：`.md`
- 纯文本：`.txt`
- JSON：`.json`
- CSV：`.csv`

每个文件包含本轮运行生成的唯一标记。读取结果必须包含该标记和预期业务内容，禁止只断言 HTTP 200。

### 3.2 文档类

- PDF：`.pdf`
- Word：`.docx`
- Excel：`.xlsx`

使用仓库内固定的小型合成 fixture，不包含真实用户数据。上传后必须校验文件名、类型、大小和唯一测试内容；若服务端采用异步抽取，则在限定时间内轮询到成功或失败终态。超时、解析失败和不可诊断响应均判为失败，不使用 skip/xfail 掩盖。

### 3.3 异常输入

- 零字节空文件。
- 扩展名与实际内容不一致的伪造文件。
- 缺少 multipart `file` 字段。

服务端必须明确拒绝或返回可诊断的业务状态，禁止出现 500。

## 4. API 测试设计

新增 `spec-kit-autotest/tests/api/documents.spec.js`，覆盖以下场景：

1. 单文档完整生命周期：上传成功、返回唯一 ID、元数据正确、列表可见、读取内容一致、删除后列表不可见。
2. 七种正常格式参数化测试：逐个验证上传、元数据和读取/解析结果。
3. 多文档性能：并发度固定为 3，上传 10 份 1MB Markdown；每份内容和名称均唯一。
4. 未认证上传与读取必须被拒绝。
5. 不存在文档 ID 必须返回明确 4xx 或业务失败，禁止 500。
6. 空文件、伪扩展名和缺文件字段必须被拒绝或返回明确业务失败，禁止 500。
7. 权限边界：`xuhp` 创建测试文档，使用 `root` 管理员身份验证管理员访问语义；不得把管理员可读取误判成普通用户横向越权。普通用户间横向越权不在本次范围，因为目前没有第二套 member 账号。

任何上传成功并取得 ID 的资源必须立即登记，在 `finally` 中逐个调用删除接口。清理失败必须使测试失败，禁止吞异常。

## 5. 性能口径

性能样本统一使用 10 份 1MB Markdown，避免不同格式解析成本污染基线。

- 并发度：3。
- 上传样本数：10。
- 读取样本数：10。
- 上传 P95：不超过 3000ms。
- 读取 P95：不超过 1000ms。
- 上传与读取失败率：0%。

P95 使用 nearest-rank：对耗时升序排序，取 `ceil(0.95 × N)` 对应样本。测试输出样本数、最小值、中位数、P95、最大值和失败率。每次请求除性能阈值外，还必须验证业务成功、文档 ID 唯一以及读取内容属于对应上传文件。

## 6. UI 测试设计

新增 `spec-kit-autotest/tests/ui/documents.spec.js`：

1. 进入 `/docs?scope=personal`，验证文档中心标题、个人文档标签和上传入口。
2. 上传唯一 Markdown fixture，验证对应文档卡片出现且元数据与文件名匹配。
3. 点击文档卡片，验证预览区域包含唯一内容标记。
4. 测试结束后通过 API 精确删除本轮创建的文档。

UI 测试不承担接口 P95 结论，只验证用户可操作性和前后端联通。

## 7. 文件、脚本与执行边界

- 新增 `spec-kit-autotest/tests/api/documents.spec.js`。
- 新增 `spec-kit-autotest/tests/ui/documents.spec.js`。
- 新增 `spec-kit-autotest/tests/fixtures/documents/` 下的合成格式 fixture。
- 按需要扩展测试工具以提供统计计算和 fixture 构造，但不做无关重构。
- 在 `spec-kit-autotest/scripts/run-suite.js` 增加独立 `documents` 套件。

`documents` 套件要求：

- `TEST_ENV_TYPE=isolated`
- `ALLOW_STATEFUL_TESTS=true`

它不进入 production-like 只读 CI，也不自动并入 destructive 套件。

## 8. 验收标准

- happy path、边界值、失败路径和异常输入均有业务断言。
- 七种正常格式全部有独立可诊断结果。
- 多文档上传和读取满足已确认 P95 与零失败率要求。
- 所有本轮创建且成功返回 ID 的文档均完成清理。
- ESLint、单元测试、文档 API 套件和文档 UI Chromium 套件通过。
- 测试报告不包含密码、token 或真实用户文档内容。
