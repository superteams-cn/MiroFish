/** 鉴权令牌的本地存储（P1：localStorage + Bearer）。
 *
 * 安全权衡：access/refresh 均存 localStorage，实现最简、易调试；代价是对 XSS 的
 * 抗性弱于 httpOnly cookie。产品尚未上线，后续可平滑切到 cookie 方案。
 */

const ACCESS_KEY = 'sf_access_token'
const REFRESH_KEY = 'sf_refresh_token'

export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(ACCESS_KEY)
  } catch {
    return null
  }
}

export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY)
  } catch {
    return null
  }
}

export function setTokens(accessToken: string, refreshToken?: string): void {
  try {
    localStorage.setItem(ACCESS_KEY, accessToken)
    if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken)
  } catch {
    /* 隐私模式等场景静默失败 */
  }
}

export function clearTokens(): void {
  try {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  } catch {
    /* noop */
  }
}
