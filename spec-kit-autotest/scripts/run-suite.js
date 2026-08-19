const { spawnSync } = require('child_process');
const env = require('../config/env');

const suite = process.argv[2];
const definitions = {
  readonly: { args: ['--project=api', 'tests/api/auth.spec.js', '--grep', '登录-|会话校验|获取当前用户'], remote: true },
  stateful: { args: ['--project=api', 'tests/api/requirements.spec.js', 'tests/api/sdd.spec.js'], stateful: true },
  ai: { args: ['--project=api', 'tests/api/core-exec4.spec.js'], ai: true },
  destructive: { args: ['--project=api', '--grep', '删除|归档'], destructive: true },
  ui: { args: ['--project=ui-chromium', '--project=ui-firefox'], stateful: true },
};
const selected = definitions[suite];
if (!selected) throw new Error(`未知测试套件: ${suite}`);

if (selected.stateful && !env.allowStatefulTests) {
  throw new Error('CONFIG_ERROR: stateful 测试需要 ALLOW_STATEFUL_TESTS=true');
}
if (selected.ai && !env.runAITests) {
  throw new Error('CONFIG_ERROR: AI 测试需要 RUN_AI_TESTS=true');
}
if (selected.destructive && !(env.environmentType === 'isolated' && env.allowDestructiveTests)) {
  throw new Error('CONFIG_ERROR: destructive 测试仅允许 isolated 且 ALLOW_DESTRUCTIVE_TESTS=true');
}
if ((selected.stateful || selected.destructive) && env.environmentType === 'production-like') {
  throw new Error('CONFIG_ERROR: production-like 禁止有状态或破坏性测试');
}

if (process.env.SAFETY_CHECK_ONLY === 'true') {
  console.log(`安全检查通过: suite=${suite}, environment=${env.environmentType}`);
  process.exit(0);
}

const headed = process.env.TEST_HEADED === 'true' ? ['--headed'] : [];
const result = spawnSync('npx', ['playwright', 'test', ...selected.args, ...headed], { stdio: 'inherit', env: process.env });
process.exit(result.status === null ? 2 : result.status);
