/** 模拟交易数据接口；私有缓存按会员隔离。 */
import type {
  ApiResponse,
  AutoTradeRead,
  ApplicationRead,
  TradeTiming,
  PageResult,
  PortfolioRead,
  TradeInput,
  TradePreview,
  TradeRead,
  TradeHistoryItem,
  TradeHistoryQuery,
} from '@project/shared'
import type { MaybeRef } from 'vue'
import { useApiBase } from './usePortalApi'

async function portfolioRequest<T>(
  path: string,
  options: Record<string, unknown> = {},
): Promise<T> {
  const { authHeaders } = useAuth()
  const response = await $fetch<ApiResponse<T>>(`/portal/me${path}`, {
    baseURL: useApiBase(),
    headers: authHeaders.value,
    ...options,
  })
  if (response.code !== 0 || response.data == null)
    throw new Error(response.message || '服务未返回数据')
  return response.data
}

export function usePortfolio() {
  const { user, authHeaders } = useAuth()
  return useAsyncData<PortfolioRead | null>(
    () => `me-portfolio-${user.value?.id ?? 'guest'}`,
    () => (user.value ? portfolioRequest<PortfolioRead>('/portfolio') : Promise.resolve(null)),
    { watch: [() => authHeaders.value.Authorization] },
  )
}
export function useTransactions(
  params: MaybeRef<number | TradeHistoryQuery>,
  enabled: MaybeRef<boolean> = true,
) {
  const { user, authHeaders } = useAuth()
  return useAsyncData<PageResult<TradeHistoryItem> | null>(
    () => `me-transactions-${user.value?.id ?? 'guest'}`,
    () =>
      user.value && unref(enabled)
        ? portfolioRequest<PageResult<TradeHistoryItem>>('/records', {
            query:
              typeof unref(params) === 'number'
                ? { page: unref(params), page_size: 20 }
                : unref(params),
          })
        : Promise.resolve(null),
    { watch: [() => unref(params), () => unref(enabled), () => authHeaders.value.Authorization] },
  )
}
/** 公开基金页面只查询代码，不下载个人资产明细。 */
export function getHeldFundCodes() {
  return portfolioRequest<string[]>('/holding-codes')
}
export function previewTrade(input: TradeInput) {
  return portfolioRequest<TradePreview>('/transactions/preview', { method: 'POST', body: input })
}
export function confirmTrade(input: {
  request: TradeInput
  preview_hash: string
  request_key: string
}) {
  return portfolioRequest<TradeRead>('/transactions', { method: 'POST', body: input })
}
export function voidTrade(id: number, reason: string) {
  return portfolioRequest<TradeRead>(`/transactions/${id}/void`, {
    method: 'POST',
    body: { reason },
  })
}
export function tradeError(error: unknown): string {
  const data = (error as { data?: { message?: string; detail?: unknown } })?.data
  return data?.message || (error instanceof Error ? error.message : '操作失败，请稍后重试')
}

/** 对应申请时刻的净值日，不使用列表上的最近净值日。 */
export function checkTradeTiming(input: {
  code: string
  submitted_at: string
  pricing_rule: string
}) {
  return portfolioRequest<TradeTiming>('/transactions/timing', { method: 'POST', body: input })
}
export function saveTradeApplication(input: Record<string, unknown>) {
  return portfolioRequest<ApplicationRead>('/applications', { method: 'POST', body: input })
}
export function useTradeApplications() {
  const { user, authHeaders } = useAuth()
  return useAsyncData<ApplicationRead[]>(
    () => `me-applications-${user.value?.id ?? 'guest'}`,
    () => (user.value ? portfolioRequest<ApplicationRead[]>('/applications') : Promise.resolve([])),
    { watch: [() => authHeaders.value.Authorization] },
  )
}
export function cancelTradeApplication(id: number) {
  return portfolioRequest(`/applications/${id}/cancel`, { method: 'POST' })
}

/** 金额/时间自动查询并计算；费用或净值未知时保留待处理。 */
export function saveAutomaticTrade(input: Record<string, unknown>) {
  return portfolioRequest<AutoTradeRead>('/auto-transactions', { method: 'POST', body: input })
}

export function deleteTradeRecord(item: TradeHistoryItem) {
  const path = item.record_type === 'transaction' ? 'transactions' : 'applications'
  return portfolioRequest(`/${path}/${item.id}`, { method: 'DELETE' })
}
