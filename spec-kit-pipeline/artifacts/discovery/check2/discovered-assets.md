# Discovered Assets

- Scan run: `scan-local`
- Environment: `isolated`

## Summary

- endpoints: 6
- observed_flows: 0
- source_rules: 11
- tests: 15
- unreadable: 0

## Endpoints

### `GET /auth/login`
- risk: `readonly`; confidence: `medium`
- responses: `unknown`
- evidence: `ev-a9fd77c8d51d65ea`
### `GET /auth/session`
- risk: `readonly`; confidence: `medium`
- responses: `unknown`
- evidence: `ev-6066b704592cb178`
### `GET /requirements`
- risk: `readonly`; confidence: `medium`
- responses: `unknown`
- evidence: `ev-8c7d90d6afb1431a`
### `GET /sdd/projects`
- risk: `readonly`; confidence: `medium`
- responses: `unknown`
- evidence: `ev-2d5a3f43a22be600`
### `GET /jobs`
- risk: `readonly`; confidence: `medium`
- responses: `unknown`
- evidence: `ev-9addfda6eee469b3`
### `GET /quality-gates`
- risk: `readonly`; confidence: `medium`
- responses: `unknown`
- evidence: `ev-aeaf63539eabc42d`

## Existing Tests

- `spec-kit-autotest/tests/api/auth.spec.js`: 登录-正确凭据返回 token, 登录-错误密码返回失败, 登录-空字段校验, 会话校验-未登录返回401, 会话校验-已登录返回用户信息, 获取当前用户信息, 登出-接口可调用, 注册-空字段被拒绝, 注册-正常凭据可注册（@smoke）
- `spec-kit-autotest/tests/api/converted_demo.spec.js`: 字段校验-正常数据创建成功, 字段校验-标题为空被拒, 字段校验-标题超长被拒或截断, 横向越权-未登录访问用户数据返回401, 横向越权-member访问管理后台被拒绝, 横向越权-未登录访问需求列表返回401, Prompt注入-对话发送注入串不越权
- `spec-kit-autotest/tests/api/core-exec.spec.js`: TC-SSE-001 作业列表与详情结构完整, TC-SSE-001 作业详情-未知id返回错误而非崩溃, TC-SEC-001 未登录访问受保护接口返回401, TC-SEC-001 member访问管理后台被拒绝, TC-SEC-001 导出响应不含明文密钥字段, TC-REQ-APP-002 C级需求自批审批被拒, TC-REQ-APP-003 重复转SDD幂等, TC-TASK-001 SDD任务接口结构可达且非纯Markdown, TC-SDD-005 质量门禁缺必填字段被拦截, TC-SDD-005 质量门禁绑定需求后可调用
- `spec-kit-autotest/tests/api/core-exec2.spec.js`: TC-REQ-APP-001 C级需求单角色审批不能直接完成, TC-SDD-001 新项目阶段状态未解锁, TC-SDD-002 Clarify分析接口可达且含问题结构, TC-IMPL-001 未批准任务执行被拒或需前置门禁, TC-SSE-003 作业状态可查询且未知id不崩溃, TC-HAR-001 无权限客户端审批类操作被拒, TC-HAR-001 匿名访问需求操作被拒
- `spec-kit-autotest/tests/api/core-exec3.spec.js`: TC-SDD-003 产物更新接口缺前置时受控失败, TC-SDD-003 归档接口可达（非AI）, TC-SDD-004 未认证访问验证接口被拒, TC-TASK-002 任务接口可达且结构正确, TC-TASK-002 未批准任务执行被拦截, TC-TASK-003 任务重生成缺前置时受控失败, TC-SSE-002 作业列表重复查询幂等, TC-HAR-003 无权限访问审批类接口被拒, TC-HAR-004 风险接受接口缺关键字段被拒
- `spec-kit-autotest/tests/api/core-exec4.spec.js`: TC-AI-REQ-003 注入串被受理但不崩溃, TC-REC-001 数据导出JSON可解析且关键集合存在
- `spec-kit-autotest/tests/api/requirements.spec.js`: 创建需求-成功, 创建需求-必填项缺失被拒, 需求列表-个人空间, 需求列表-团队空间, 需求详情-存在, 需求详情-不存在的ID, 需求状态流转-提交审核, 需求删除-成功, 越权-未登录访问需求列表
- `spec-kit-autotest/tests/api/sdd.spec.js`: 创建SDD项目-成功, SDD项目列表-个人空间, SDD项目详情, SDD项目-校验清单生成, SDD项目-归档, SDD项目-删除, 越权-未登录访问SDD列表
- `spec-kit-autotest/tests/api/security.spec.js`: 未登录访问受保护接口返回401, 未登录访问需求列表返回401, member访问管理后台接口被拒绝, SQL注入-登录接口无害探测, XSS-创建需求标题含脚本被转义或拒绝, 响应头-安全基线检查
- `spec-kit-autotest/tests/ui/inbox.spec.js`: 收件箱默认展示空状态或待办列表, 新建待办成功出现在列表, 时间过滤标签可切换, 优先级过滤可用
- `spec-kit-autotest/tests/ui/login-demo.spec.js`: ① 正确登录：不仅跳转成功，还要断言双 token 真实写入（人工灵魂）, ., ② 错误密码：必须断言, ③ 空字段提交：前端校验拦截，且不产生 token（人工灵魂）, ④ 未登录访问受保护页：应被重定向回登录页（人工灵魂，越权基线）, ⑤ 会话保持：登录后刷新页面仍保持登录态（人工灵魂，JWT 校验）
- `spec-kit-autotest/tests/ui/login.spec.js`: 正确凭据登录成功跳转收件箱（@smoke）, 错误密码提示失败且不跳转, 空字段提交被前端校验拦截, 登录成功后可访问受保护页面
- `spec-kit-autotest/tests/ui/requirements-demo.spec.js`: ① 状态筛选正确性：点, ② 状态筛选正确性：点, ③ 个人/团队空间切换：切换后页面正常加载且可切回（人工灵魂，数据隔离基线）, ④ 新建需求弹窗：21 字段表单完整呈现，含折叠面板（人工灵魂，方案 6.2 高风险区）, ⑤ 新建需求必填校验：只填标题点创建，应提示缺失必填项且不关闭弹窗（人工灵魂，防
- `spec-kit-autotest/tests/ui/requirements.spec.js`: 需求列表页加载, 新建需求-必填校验, 新建需求-完整填写创建成功
- `spec-kit-autotest/tests/unit/utils.spec.js`: env.api 统一拼接 API 前缀, 时间戳与标题生成器返回非空且带业务前缀, 各类数据生成器支持覆盖默认字段, 默认请求头包含 JSON，设置 token 后带 Bearer, GET 收到 401 时原样返回且不伪刷新, POST 收到 401 不会循环重试, assertOk 返回 data，异常结构抛出可诊断错误, 503 和 HTML 响应被分类为 ENV_ERROR, ResourceTracker 逆序清理并接受 404, ResourceTracker 报告残留资源, safeCleanup 不再静默吞掉清理失败, 成功登录后保存双 token, 登录失败抛出包含 HTTP 状态的错误
