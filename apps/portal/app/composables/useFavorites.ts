/**
 * 我的关注。
 *
 * 关注代码集合放 `useState`：筛选页每一行要判断星标、详情页要判断按钮状态，
 * 都读同一份集合，只请求一次 `/portal/favorites/codes`，避免逐行查询。
 */

import type { ApiResponse } from '@project/shared'
import { useApiBase } from './usePortalApi'

export function useFavorites() {
  const apiBase = useApiBase()
  const { isLoggedIn, authHeaders, openAuth } = useAuth()

  const codes = useState<Set<string>>('portal:fav-codes', () => new Set<string>())
  const loaded = useState<boolean>('portal:fav-loaded', () => false)
  const pending = useState<boolean>('portal:fav-pending', () => false)

  const count = computed(() => codes.value.size)

  function isFavorited(code: string): boolean {
    return codes.value.has(code)
  }

  async function load(force = false): Promise<void> {
    if (!isLoggedIn.value) {
      codes.value = new Set<string>()
      loaded.value = false
      return
    }
    if (loaded.value && !force) return
    try {
      const res = await $fetch<ApiResponse<string[]>>('/portal/favorites/codes', {
        baseURL: apiBase,
        headers: authHeaders.value,
      })
      codes.value = new Set(res.data ?? [])
      loaded.value = true
    } catch {
      // 拉取失败不阻断页面，星标显示为未关注即可
      loaded.value = false
    }
  }

  /**
   * 切换关注状态。返回切换后的状态；未登录时唤起登录弹窗并返回 null。
   *
   * 采用乐观更新：先改本地集合让 UI 立刻响应，失败再整体回滚。
   */
  async function toggle(code: string): Promise<boolean | null> {
    if (!isLoggedIn.value) {
      openAuth('login')
      return null
    }

    const snapshot = new Set(codes.value)
    const wasFavorited = snapshot.has(code)

    const next = new Set(snapshot)
    if (wasFavorited) next.delete(code)
    else next.add(code)
    codes.value = next

    pending.value = true
    try {
      if (wasFavorited) {
        await $fetch(`/portal/favorites/${code}`, {
          baseURL: apiBase,
          method: 'DELETE',
          headers: authHeaders.value,
        })
      } else {
        await $fetch('/portal/favorites', {
          baseURL: apiBase,
          method: 'POST',
          body: { code },
          headers: authHeaders.value,
        })
      }
      return !wasFavorited
    } catch (err) {
      codes.value = snapshot
      throw err
    } finally {
      pending.value = false
    }
  }

  /** 退出登录后清空，避免下一个账号看到上一个人的星标 */
  function reset() {
    codes.value = new Set<string>()
    loaded.value = false
  }

  return { codes, count, pending, loaded, isFavorited, load, toggle, reset }
}
