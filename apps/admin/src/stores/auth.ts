import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  STORAGE_KEYS,
  type LoginPayload,
  type StaffUser,
  type TokenResponse,
} from '@project/shared'

import { authApi } from '@/api'

/**
 * 登录态：token 存 localStorage，用户信息存内存（刷新后重新拉取）。
 * 这里的是后台员工账号（staff_users 表），与门户会员体系完全分离。
 */
export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string>(localStorage.getItem(STORAGE_KEYS.accessToken) ?? '')
  const currentUser = ref<StaffUser | null>(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => Boolean(accessToken.value))
  const displayName = computed(
    () => currentUser.value?.full_name || currentUser.value?.username || '未登录',
  )
  const isSuperuser = computed(() => currentUser.value?.is_superuser ?? false)

  function persistTokens(tokens: TokenResponse) {
    accessToken.value = tokens.access_token
    localStorage.setItem(STORAGE_KEYS.accessToken, tokens.access_token)
    localStorage.setItem(STORAGE_KEYS.refreshToken, tokens.refresh_token)
  }

  async function login(payload: LoginPayload) {
    loading.value = true
    try {
      const tokens = await authApi.login(payload)
      persistTokens(tokens)
      await fetchProfile()
    } finally {
      loading.value = false
    }
  }

  async function fetchProfile() {
    if (!accessToken.value) return
    currentUser.value = await authApi.me()
  }

  async function logout() {
    const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken)
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken)
      } catch {
        // Local credentials are cleared even if the server session already expired.
      }
    }
    accessToken.value = ''
    currentUser.value = null
    localStorage.removeItem(STORAGE_KEYS.accessToken)
    localStorage.removeItem(STORAGE_KEYS.refreshToken)
  }

  return {
    accessToken,
    currentUser,
    loading,
    isLoggedIn,
    isSuperuser,
    displayName,
    login,
    fetchProfile,
    logout,
  }
})
