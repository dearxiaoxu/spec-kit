/**
 * API 请求客户端
 * 基于 Playwright request context 封装 REST 调用
 * 保存 JWT 双 token；后端无已确认 refresh 契约，401 原样返回，不做伪刷新
 */
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
   * 发起请求。401 不自动重试，避免继续使用旧 token 制造误判。
   */
  async request_(method, url, { data, params, headers } = {}) {
    const res = await this.request[method](url, {
      data,
      params,
      headers: this.headers(headers),
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
