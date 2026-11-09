/**
 * Axios 实例：统一 baseURL、鉴权头、错误提示与 401 处理。
 * 业务层只关心 data，不关心 {code, message} 包装。
 */
import axios, { type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { BIZ_CODE, STORAGE_KEYS, type ApiResponse, type TokenResponse } from '@project/shared'

export class BusinessError extends Error {
  code: number
  constructor(code: number, message: string) {
    super(message)
    this.name = 'BusinessError'
    this.code = code
  }
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
})
let refreshInFlight: Promise<TokenResponse> | null = null

// 请求拦截：注入 access token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem(STORAGE_KEYS.accessToken)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：401 时单次续期并重放请求；刷新令牌失效后清除本地会话。
http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status
    if (status === 401) {
      const original = error.config as
        (InternalAxiosRequestConfig & { _authRetried?: boolean }) | undefined
      const authEndpoint = /\/admin\/auth\/(login|refresh|logout)(?:\?|$)/.test(original?.url ?? '')
      const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken)
      if (original && !original._authRetried && !authEndpoint && refreshToken) {
        original._authRetried = true
        refreshInFlight ??= axios
          .post<ApiResponse<TokenResponse>>(
            `${import.meta.env.VITE_API_BASE_URL ?? '/api/v1'}/admin/auth/refresh`,
            { refresh_token: refreshToken },
            { timeout: 15_000 },
          )
          .then((response) => {
            if (response.data.code !== BIZ_CODE.ok || !response.data.data) {
              throw new BusinessError(response.data.code, response.data.message || '续期失败')
            }
            return response.data.data
          })
          .finally(() => {
            refreshInFlight = null
          })
        try {
          const tokens = await refreshInFlight
          localStorage.setItem(STORAGE_KEYS.accessToken, tokens.access_token)
          localStorage.setItem(STORAGE_KEYS.refreshToken, tokens.refresh_token)
          original.headers.Authorization = `Bearer ${tokens.access_token}`
          return await http.request(original)
        } catch {
          // Fall through to local logout when rotation fails.
        }
      }

      localStorage.removeItem(STORAGE_KEYS.accessToken)
      localStorage.removeItem(STORAGE_KEYS.refreshToken)
      if (!location.pathname.startsWith('/login')) {
        ElMessage.warning('登录已过期，请重新登录')
        location.href = `/login?redirect=${encodeURIComponent(location.pathname)}`
      }
    } else if (status && status >= 500) {
      ElMessage.error('服务异常，请稍后重试')
    }
    return Promise.reject(error)
  },
)

/**
 * 统一请求方法：解包业务响应，code!=0 抛 BusinessError。
 */
export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const response = await http.request<ApiResponse<T>>(config)
  const body = response.data

  if (body.code !== BIZ_CODE.ok) {
    const message = body.message || '请求失败'
    ElMessage.error(message)
    throw new BusinessError(body.code, message)
  }
  return body.data as T
}

export const api = {
  get: <T>(url: string, params?: unknown) => request<T>({ method: 'GET', url, params }),
  post: <T>(url: string, data?: unknown) => request<T>({ method: 'POST', url, data }),
  put: <T>(url: string, data?: unknown) => request<T>({ method: 'PUT', url, data }),
  patch: <T>(url: string, data?: unknown) => request<T>({ method: 'PATCH', url, data }),
  delete: <T>(url: string) => request<T>({ method: 'DELETE', url }),
}

export default http
