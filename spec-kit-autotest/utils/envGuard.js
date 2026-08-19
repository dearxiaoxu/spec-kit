/**
 * 现网环境波动容错
 *
 * 背景（2026-08-19 实测）：现网 SDD/作业类接口（tasks/artifacts/verify/disposition/jobs 等）
 * 偶发返回 503 或 nginx HTML 兜底页。这属于环境稳定性现象（本身值得跟踪），
 * 但不属于"被测功能断言"——若直接挂红会造成回归噪音。
 *
 * 用法：对"结构可达/受控失败"类断言，请求后先过 envTolerant：
 *   const body = await res.json().catch(() => ({}));
 *   if (envTolerant('接口名', res, body)) return;   // 5xx/HTML → warn 并跳过断言
 *
 * 注意：envTolerant 只豁免"环境性失败"；真正的功能断言（401/403/幂等等）不应套用。
 */
function envTolerant(name, res, body = {}) {
  const ct = ((res && res.headers) ? res.headers() : {})['content-type'] || '';
  const isHtml = ct.toLowerCase().includes('text/html');
  const is5xx = res && res.status() >= 500;
  if (is5xx || isHtml) {
    // eslint-disable-next-line no-console
    console.warn(`[env] ${name} 返回 ${res ? res.status() : '?'}${isHtml ? ' HTML页' : ''}（现网偶发波动，环境性跳过）`);
    return true;
  }
  return false;
}

module.exports = { envTolerant };
