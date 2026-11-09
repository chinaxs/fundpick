/**
 * 会员中心数据获取（工作台 / 个人设置）。
 *
 * 全部请求带 authHeaders（Bearer access token），SSR 阶段从 cookie 读取，
 * 因此首屏就能渲染私有数据，不会先闪"未登录"再水合。
 */

import type { MaybeRef } from 'vue'
import type {
  ApiResponse,
  DashboardData,
  PortalUser,
  PositionCreatePayload,
  PositionItem,
  PositionListData,
  PositionUpdatePayload,
  ProfileUpdatePayload,
  PortfolioSummary,
} from '@project/shared'
import { useApiBase } from './usePortalApi'
import { useAuth } from './useAuth'

interface MessageResult {
  message: string
}

const EMPTY_DASHBOARD: DashboardData = {
  period: '1y',
  portfolio_summary: {
    estimated_count: 0,
    calculated_count: 0,
    pending_count: 0,
    count: 0,
    total_amount: 0,
    total_market_value: null,
    total_profit: null,
    profit_rate: null,
    valued_count: 0,
    realized_profit: 0,
    total_return: null,
    total_buy_amount: 0,
    total_sell_amount: 0,
    fees: 0,
    transaction_count: 0,
    legacy_count: 0,
  },
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
  position_summary: {
    count: 0,
    total_amount: 0,
    total_market_value: null,
    total_profit: null,
    profit_rate: null,
    valued_count: 0,
  },
}

/** 工作台统计：period 为 ref 时切换区间会自动重新请求 */
export function useDashboard(period: MaybeRef<string> = '1y') {
  const { authHeaders, user } = useAuth()
  return useAsyncData<DashboardData>(
    () => `me-dashboard-${user.value?.id ?? 'guest'}`,
    async () => {
      if (!authHeaders.value.Authorization) return { ...EMPTY_DASHBOARD }
      const res = await $fetch<ApiResponse<DashboardData>>('/portal/me/dashboard', {
        baseURL: useApiBase(),
        headers: authHeaders.value,
        query: { period: unref(period) },
      })
      if (res.code !== 0 || !res.data) throw new Error(res.message || '工作台数据加载失败')
      return { ...res.data, portfolio_summary: res.data.portfolio_summary ?? null }
    },
    {
      watch: [() => unref(period), () => authHeaders.value.Authorization],
      transform: (value): DashboardData => ({
        ...value,
        portfolio_summary: value.portfolio_summary ?? null,
      }),
    },
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

// ---------------------------------------------------------------- 模拟持仓
/** 持仓页数据：明细 + 汇总一次取回；净值按买入日期自动取，用户不填净值 */
export function usePositions() {
  const { authHeaders, user } = useAuth()
  return useAsyncData<PositionListData>(
    () => `me-positions-${user.value?.id ?? 'guest'}`,
    async () => {
      if (!authHeaders.value.Authorization) {
        return {
          items: [],
          summary: {
            count: 0,
            total_amount: 0,
            total_market_value: null,
            total_profit: null,
            profit_rate: null,
            valued_count: 0,
          },
        }
      }
      const res = await $fetch<ApiResponse<PositionListData>>('/portal/me/positions', {
        baseURL: useApiBase(),
        headers: authHeaders.value,
      })
      return (
        res.data ?? {
          items: [],
          summary: {
            count: 0,
            total_amount: 0,
            total_market_value: null,
            total_profit: null,
            profit_rate: null,
            valued_count: 0,
          },
        }
      )
    },
  )
}

/** 新增模拟持仓：只录金额 + 日期，份额由服务端折算 */
export function createPosition(payload: PositionCreatePayload): Promise<PositionItem> {
  return meRequest<PositionItem>('/positions', { method: 'POST', body: payload })
}

export function updatePosition(id: number, payload: PositionUpdatePayload): Promise<PositionItem> {
  return meRequest<PositionItem>(`/positions/${id}`, { method: 'PATCH', body: payload })
}

export function deletePosition(id: number): Promise<MessageResult> {
  return meRequest<MessageResult>(`/positions/${id}`, { method: 'DELETE' })
}
