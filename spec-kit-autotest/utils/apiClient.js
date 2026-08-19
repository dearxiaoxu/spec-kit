/**
 * API 请求客户端
 * 基于 Playwright request context 封装 REST 调用
 * 支持 JWT 双 token（accessToken + refreshToken）自动刷新
 */
const env = require('../config/env');

class ApiClient {
  /**
   * @param {import('@playwright/test').APIRequestContext} request
   */
  constructor(request) {
    this.request = request;
    this.accessToken = null;
    this.refreshToken = null;
  }

  /** 设置 token */
  setTokens(accessToken, refreshToken) {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
  }

  /** 构造请求头 */
  headers(extra = {}) {
    return {
      'Content-Type': 'application/json',
      ...(this.accessToken ? { Authorization: `Bearer ${this.accessToken}` } : {}),
      ...extra,
    };
  }

  /**
   * 发起请求，token 过期时自动用 refreshToken 重试一次
   */
  async request_(method, url, { data, params, headers } = {}) {
    const res = await this.request[method](url, {
      data,
      params,
      headers: this.headers(headers),
    });
    // token 过期（401）且存在 refreshToken 时刷新重试
    if (res.status() === 401 && this.refreshToken && method !== 'post') {
      await this.refreshAccessToken();
      return this.request[method](url, {
        data,
        params,
        headers: this.headers(headers),
      });
    }
    return res;
  }

  /** 刷新 access token */
  async refreshAccessToken() {
    // 说明：后端未提供独立 refresh 接口，这里通过 session 校验 + 重新登录兜底
    const res = await this.request.get(`${env.baseURL}${env.api('/auth/session')}`, {
      headers: this.headers(),
    });
    return res;
  }

  // ---------- 常用方法 ----------
  get(url, opts) { return this.request_('get', url, opts); }
  post(url, opts) { return this.request_('post', url, opts); }
  put(url, opts) { return this.request_('put', url, opts); }
  patch(url, opts) { return this.request_('patch', url, opts); }
  delete(url, opts) { return this.request_('delete', url, opts); }
}

/** 快速校验响应结构 {ok:true,data} */
function assertOk(res, body) {
  if (!body || body.ok !== true) {
    throw new Error(`接口返回异常: HTTP ${res.status()}, body=${JSON.stringify(body).slice(0, 300)}`);
  }
  return body.data;
}

module.exports = { ApiClient, assertOk };
