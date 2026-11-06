/**
 * 会员中心数据获取（工作台 / 个人设置）。
 *
 * 全部请求带 authHeaders（Bearer access token），SSR 阶段从 cookie 读取，
 * 因此首屏就能渲染私有数据，不会先闪"未登录"再水合。
 */

import type { MaybeRef } from 'vue'
import type { ApiResponse, DashboardData, PortalUser, ProfileUpdatePayload } from '@project/shared'
import { useApiBase } from './usePortalApi'
import { useAuth } from './useAuth'

interface MessageResult {
  message: string
}

const EMPTY_DASHBOARD: DashboardData = {
  period: '1y',
  summary: {
    total_funds: 0,
    avg_return: null,
    positive_ratio: null,
    avg_sharpe: null,
    best_return: null,
    added_last_7_days: 0,
    metric_coverage: 0,
    latest_nav_date: null,
  },
  type_distribution: [],
  risk_distribution: [],
  sector_distribution: [],
  return_buckets: [],
  top_funds: [],
  recent_funds: [],
}

/** 工作台统计：period 为 ref 时切换区间会自动重新请求 */
export function useDashboard(period: MaybeRef<string> = '1y') {
  const { authHeaders } = useAuth()
  return useAsyncData<DashboardData>(
    'me-dashboard',
    async () => {
      if (!authHeaders.value.Authorization) return { ...EMPTY_DASHBOARD }
      const res = await $fetch<ApiResponse<DashboardData>>('/portal/me/dashboard', {
        baseURL: useApiBase(),
        headers: authHeaders.value,
        query: { period: unref(period) },
      })
      return res.data ?? { ...EMPTY_DASHBOARD }
    },
    { watch: [() => unref(period)] },
  )
}

async function meRequest<T>(path: string, options: Record<string, unknown>): Promise<T> {
  const { authHeaders } = useAuth()
  const res = await $fetch<ApiResponse<T>>(`/portal/me${path}`, {
    baseURL: useApiBase(),
    headers: { ...authHeaders.value, 'Content-Type': 'application/json' },
    ...options,
  })
  return res.data as T
}

/** 更新资料 */
export function updateMyProfile(payload: ProfileUpdatePayload): Promise<PortalUser> {
  return meRequest<PortalUser>('', { method: 'PATCH', body: payload })
}

/** 修改密码 */
export function changeMyPassword(oldPassword: string, newPassword: string): Promise<MessageResult> {
  return meRequest<MessageResult>('/change-password', {
    method: 'POST',
    body: { old_password: oldPassword, new_password: newPassword },
  })
}

/** 注销账号（服务端二次校验密码） */
export function deactivateMyAccount(password: string): Promise<MessageResult> {
  return meRequest<MessageResult>('/deactivate', {
    method: 'POST',
    body: { password },
  })
}
