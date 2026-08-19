/**
 * 环境配置加载
 * 读取 .env 环境变量，提供统一配置对象
 */
const dotenv = require('dotenv');
const path = require('path');

dotenv.config({ path: path.resolve(__dirname, '../.env') });

const env = {
  /** 目标环境地址 */
  baseURL: process.env.BASE_URL || 'https://106.54.60.191',
  /** member 测试账号 */
  username: process.env.USERNAME || 'Xuhp',
  password: process.env.PASSWORD || '',
  /** admin 账号（管理后台用例） */
  adminUsername: process.env.ADMIN_USERNAME || 'admin',
  adminPassword: process.env.ADMIN_PASSWORD || '',
  /** 是否忽略 HTTPS 证书 */
  ignoreHTTPSErrors: process.env.IGNORE_HTTPS_ERRORS !== 'false',
  /** 全局超时 */
  timeout: parseInt(process.env.TIMEOUT || '30000', 10),
  /** 是否执行 AI 用例（会产生模型调用费用） */
  runAITests: process.env.RUN_AI_TESTS === 'true',
  /** 环境类型：production-like / isolated / local */
  environmentType: process.env.TEST_ENV_TYPE || 'production-like',
  allowStatefulTests: process.env.ALLOW_STATEFUL_TESTS === 'true',
  allowDestructiveTests: process.env.ALLOW_DESTRUCTIVE_TESTS === 'true',
  environmentErrorThreshold: parseInt(process.env.ENV_ERROR_THRESHOLD || '3', 10),
  /** API 前缀 */
  apiPrefix: '/api/v1',
};

/** 组装完整 API 路径 */
env.api = (path) => `${env.apiPrefix}${path}`;

module.exports = env;
