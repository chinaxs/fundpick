/**
 * 持仓工具的数据层：导入、公司行为、收益核对、导出。
 *
 * 页面和组件只调用这里的函数，URL 与解包集中在一处；
 * 所有请求带门户令牌（这些接口都需要登录）。
 */
import type { ApiResponse } from '@project/shared'

export interface ImportRowInput {
  code: string
  confirmed_on: string
  shares?: string | null
  amount?: string | null
  nav?: string | null
  platform?: string | null
  note?: string | null
}

export interface ImportRowError {
  index: number
  code: string | null
  reason: string
}

export interface ImportResult {
  created: number
  dry_run: boolean
  errors: ImportRowError[]
  imported: Record<string, string>[]
}

export interface FlowRecord {
  id: number
  code: string
  fund_name: string
  kind: string
  kind_label: string
  effective_on: string
  cash_amount: number | null
  /** 转换转出的实际结转净额；与 cash_amount 的差是转换费用 */
  net_amount?: number | null
  shares_delta: number | null
  nav: number | null
  ratio: number | null
  target_code: string | null
  /** 归属平台：再投/分红/转换只作用于该平台 */
  platform: string | null
  note: string | null
  created_at: string
}

export interface FlowPayload {
  code: string
  kind: string
  effective_on: string
  cash_amount?: number | null
  shares_delta?: number | null
  nav?: number | null
  ratio?: number | null
  target_code?: string | null
  /** 转换转入的实际份额与净值：转入份额由对手基金净值决定 */
  target_shares?: number | null
  target_nav?: number | null
  target_cash_amount?: number | null
  /** 归属平台：单平台自动识别，多平台持有时必须指定 */
  platform?: string | null
  /** 幂等键：网络重试不会重复记一笔 */
  request_key?: string | null
  note?: string | null
}

export interface ReconciliationFund {
  code: string
  name: string
  ledger_shares: number
  ledger_cost: number
  flow_shares_delta: number
  flow_cash: number
  expected_shares: number
  note: string | null
}

export interface Reconciliation {
  funds: ReconciliationFund[]
  invested: number
  redeemed: number
  dividends: number
  realized_profit: number
  note: string
  generated_at: string
}

export function portfolioToday() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

export function usePortfolioTools() {
  const apiBase = useApiBase()
  const { authHeaders } = useAuth()

  async function request<T>(path: string, options: Record<string, unknown> = {}) {
    const res = await $fetch<ApiResponse<T>>(path, {
      baseURL: apiBase,
      headers: authHeaders.value,
      ...options,
    })
    return res.data as T
  }

  return {
    reconciliation: () => request<Reconciliation>('/portal/me/portfolio/reconciliation'),
    listFlows: () => request<FlowRecord[]>('/portal/me/portfolio/flows'),
    previewImport: (rows: ImportRowInput[]) =>
      request<ImportResult>('/portal/me/portfolio/import', {
        method: 'POST',
        body: { rows, dry_run: true },
      }),
    commitImport: (rows: ImportRowInput[]) =>
      request<ImportResult>('/portal/me/portfolio/import', {
        method: 'POST',
        body: { rows, dry_run: false },
      }),
    addFlow: (payload: FlowPayload) =>
      request<FlowRecord>('/portal/me/portfolio/flows', { method: 'POST', body: payload }),
    removeFlow: (id: number) =>
      request<unknown>(`/portal/me/portfolio/flows/${id}`, { method: 'DELETE' }),
    /** 导出需要带令牌，不能用 <a download>，改为取 blob 再触发下载 */
    async exportCsv() {
      const response = await fetch('/api/v1/portal/me/portfolio/export', {
        headers: authHeaders.value,
      })
      if (!response.ok) throw new Error('导出失败，请稍后重试')
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `portfolio-${new Date().toISOString().slice(0, 10)}.csv`
      link.click()
      URL.revokeObjectURL(url)
    },
  }
}
