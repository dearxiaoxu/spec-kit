# 获授权隔离测试环境配置设计

## 目标

将 `https://106.54.60.191` 作为用户明确授权的隔离测试目标，启用有状态、AI 和破坏性测试，同时保持账号分权、资源闭环和凭据不入库。

## 账号与配置

- `xuhp` 作为 member 自动化账号，用于常规业务、权限和资源生命周期测试。
- `root` 作为 admin 账号，只供明确需要管理员权限的用例使用。
- 凭据仅写入被 Git 忽略的 `spec-kit-autotest/.env`，不写入源码、文档、报告或命令输出。
- 环境设置为 `TEST_ENV_TYPE=isolated`，显式开启 `ALLOW_STATEFUL_TESTS`、`ALLOW_DESTRUCTIVE_TESTS` 和 `RUN_AI_TESTS`。

## 安全边界

- destructive 套件只运行标题匹配“删除/归档”的既有用例。
- 删除和归档对象必须由同一用例当场创建，不引用固定 ID，不操作历史列表中的资源。
- 先运行安全检查，再运行 stateful，最后运行 destructive；失败时停止扩大测试范围。
- 测试报告不得包含密码或 token。

## 验收

- 配置加载结果显示 isolated 及三个开关开启，但不打印凭据。
- stateful 和 destructive 的安全检查均通过。
- 两套测试执行完成，并核对退出码与清理结果。
