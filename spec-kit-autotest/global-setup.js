/**
 * 全局前置脚本（不依赖浏览器）
 * - 校验目标环境可达（HTTP 探测，自动忽略自签名证书）
 * - 校验登录页可加载
 * - 校验测试账号可登录（提前暴露环境/凭据问题）
 */
const env = require('./config/env');
const https = require('https');

/** 忽略证书的 https GET */
function httpsGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { rejectUnauthorized: false }, (res) => {
      resolve({ status: res.statusCode });
    });
    req.on('error', reject);
    req.setTimeout(15000, () => { req.destroy(new Error('timeout')); });
  });
}

/** 忽略证书的 https POST */
function httpsPost(url, data) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(data);
    const req = https.request(url, {
      method: 'POST',
      rejectUnauthorized: false,
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
    }, (res) => {
      let chunk = '';
      res.on('data', (d) => chunk += d);
      res.on('end', () => resolve({ status: res.statusCode, body: chunk.slice(0, 200) }));
    });
    req.on('error', reject);
    req.setTimeout(15000, () => { req.destroy(new Error('timeout')); });
    req.write(body);
    req.end();
  });
}

async function globalSetup() {
  console.log(`[global-setup] 目标环境: ${env.baseURL} (cert ignored: ${env.ignoreHTTPSErrors})`);

  // 1. 探测登录页
  try {
    const res = await httpsGet(`${env.baseURL}/login`);
    if (res.status >= 400) {
      console.warn(`[global-setup] 登录页 HTTP ${res.status}，请确认环境可用`);
    } else {
      console.log(`[global-setup] 登录页可达 (HTTP ${res.status})`);
    }
  } catch (e) {
    console.warn(`[global-setup] 环境不可达: ${e.message}`);
  }

  // 2. 校验测试账号可登录
  if (env.password) {
    try {
      const res = await httpsPost(`${env.baseURL}${env.api('/auth/login')}`, {
        username: env.username,
        password: env.password,
      });
      if (res.status === 200 && res.body.includes('"ok":true')) {
        console.log(`[global-setup] 账号 ${env.username} 登录验证通过`);
      } else {
        console.warn(`[global-setup] 账号 ${env.username} 登录验证失败: HTTP ${res.status}, ${res.body}`);
      }
    } catch (e) {
      console.warn(`[global-setup] 登录验证异常: ${e.message}`);
    }
  } else {
    console.log('[global-setup] 未配置密码，跳过登录验证');
  }
}

module.exports = globalSetup;
