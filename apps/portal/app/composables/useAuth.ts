/**
 * 门户登录态。
 *
 * 令牌存 cookie 而不是 localStorage：SSR 时服务端要能读到，
 * 否则首屏会先渲染"未登录"，水合后才闪成已登录。
 *
 * 双层令牌：
 * - access（2 小时）用于日常请求；
 * - refresh（7 天）在 access 过期后自动换取新的 access，
 *   避免用户每次打开页面都要重新登录。
 */

import type { ApiResponse, PortalUser, TokenBundle } from '@project/shared'
import { useApiBase } from './usePortalApi'

const ACCESS_COOKIE = 'portal_at'
const REFRESH_COOKIE = 'portal_rt'

export type AuthMode = 'login' | 'register'

export function useAuth() {
  const apiBase = useApiBase()

  const user = useState<PortalUser | null>('portal:user', () => null)
  const ready = useState<boolean>('portal:auth-ready', () => false)

  // 弹窗状态放全局：任意组件都能唤起，不需要层层传事件
  const dialogVisible = useState<boolean>('portal:auth-dialog', () => false)
  const dialogMode = useState<AuthMode>('portal:auth-mode', () => 'login')

  const accessToken = useCookie<string | null>(ACCESS_COOKIE, {
    maxAge: 60 * 60 * 2,
    sameSite: 'lax',
    path: '/',
  })
  const refreshToken = useCookie<string | null>(REFRESH_COOKIE, {
    maxAge: 60 * 60 * 24 * 7,
    sameSite: 'lax',
    path: '/',
  })

  const isLoggedIn = computed(() => user.value !== null)

  /** 需要登录的请求统一带这个头 */
  const authHeaders = computed<Record<string, string>>(() => {
    const headers: Record<string, string> = {}
    if (accessToken.value) headers.Authorization = `Bearer ${accessToken.value}`
    return headers
  })
  const displayName = computed(() => user.value?.full_name || user.value?.username || '会员')
  const avatarText = computed(() => displayName.value.slice(0, 1).toUpperCase())

  /** 统一响应的 data 可能为 null（类型上是 `T | null`），这里显式兜住 */
  function applyTokens(bundle: TokenBundle | null) {
    if (!bundle) throw new Error('服务端未返回登录凭证')
    accessToken.value = bundle.access_token
    refreshToken.value = bundle.refresh_token
  }

  function clearSession() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
  }

  async function fetchProfile(): Promise<PortalUser | null> {
    if (!accessToken.value) return null
    try {
      const res = await $fetch<ApiResponse<PortalUser>>('/portal/auth/me', {
        baseURL: apiBase,
        headers: { Authorization: `Bearer ${accessToken.value}` },
      })
      user.value = res.data
      return res.data
    } catch {
      return null
    }
  }

  async function refreshSession(): Promise<boolean> {
    if (!refreshToken.value) return false
    try {
      const res = await $fetch<ApiResponse<TokenBundle>>('/portal/auth/refresh', {
        baseURL: apiBase,
        method: 'POST',
        body: { refresh_token: refreshToken.value },
      })
      applyTokens(res.data)
      return (await fetchProfile()) !== null
    } catch {
      clearSession()
      return false
    }
  }

  /** 页面加载时恢复登录态：access 可用则直接用，过期则用 refresh 续期。 */
  async function ensureSession(): Promise<void> {
    if (ready.value) return
    if (!accessToken.value && !refreshToken.value) {
      ready.value = true
      return
    }
    const ok = (await fetchProfile()) !== null
    if (!ok) await refreshSession()
    ready.value = true
  }

  async function login(username: string, password: string): Promise<void> {
    const res = await $fetch<ApiResponse<TokenBundle>>('/portal/auth/login', {
      baseURL: apiBase,
      method: 'POST',
      body: { username, password },
    })
    applyTokens(res.data)
    await fetchProfile()
  }

  async function register(payload: {
    username: string
    email?: string
    password: string
  }): Promise<void> {
    const res = await $fetch<ApiResponse<TokenBundle>>('/portal/auth/register', {
      baseURL: apiBase,
      method: 'POST',
      body: payload,
    })
    applyTokens(res.data)
    await fetchProfile()
  }

  async function logout(): Promise<void> {
    try {
      if (refreshToken.value) {
        await $fetch('/portal/auth/logout', {
          baseURL: apiBase,
          method: 'POST',
          body: { refresh_token: refreshToken.value },
        })
      }
    } catch {
      // 服务端无状态，通知失败也不影响本地清理
    }
    clearSession()
  }

  function openAuth(mode: AuthMode = 'login') {
    dialogMode.value = mode
    dialogVisible.value = true
  }

  return {
    user,
    ready,
    isLoggedIn,
    authHeaders,
    displayName,
    avatarText,
    dialogVisible,
    dialogMode,
    ensureSession,
    fetchProfile,
    login,
    register,
    logout,
    openAuth,
  }
}
