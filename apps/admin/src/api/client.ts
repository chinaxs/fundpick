/**
 * Axios 实例：统一 baseURL、鉴权头、错误提示与 401 处理。
 * 业务层只关心 data，不关心 {code, message} 包装。
 */
import axios, { type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { BIZ_CODE, STORAGE_KEYS, type ApiResponse } from '@project/shared'

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

// 请求拦截：注入 access token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem(STORAGE_KEYS.accessToken)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：401 统一登出
http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    if (status === 401) {
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
