/**
 * 基金数据获取：与 usePortalApi 保持同一套约定（useAsyncData + 显式泛型）。
 */
import type { MaybeRef } from 'vue'
import type {
  FundHoldingQuotesResult,
  ApiResponse,
  FilterOptions,
  OverviewStats,
  ReturnDistribution,
  FundDetail,
  FundHoldingsResult,
  FundListItem,
  FundMetric,
  FundQuery,
  NavPoint,
  NavRange,
  PageResult,
} from '@project/shared'
import { useApiBase } from './usePortalApi'

/** 筛选排行。key 必须唯一——同一页面放多个榜单时传入不同 key。 */
export function useFundList(params: MaybeRef<FundQuery>, key = 'fund-list') {
  return useAsyncData<PageResult<FundListItem>>(
    key,
    async () => {
      const res = await $fetch<ApiResponse<PageResult<FundListItem>>>('/portal/funds', {
        baseURL: useApiBase(),
        query: unref(params),
      })
      return res.data ?? { items: [], total: 0, page: 1, page_size: 20 }
    },
    { watch: [() => unref(params)] },
  )
}

/** 筛选项字典（类型、风险、公司、区间、排序） */
export function useFundFilters() {
  return useAsyncData<FilterOptions>(
    'fund-filters',
    async () => {
      const res = await $fetch<ApiResponse<FilterOptions>>('/portal/funds/filters', {
        baseURL: useApiBase(),
      })
      return (
        res.data ?? {
          types: [],
          risk_levels: [],
          sectors: [],
          companies: [],
          periods: [],
          sort_fields: [],
        }
      )
    },
    { server: true },
  )
}

/** 市场概览（总数、公司数、类型分布） */
export function useOverviewStats() {
  return useAsyncData<OverviewStats>(
    'fund-overview',
    async () => {
      const res = await $fetch<ApiResponse<OverviewStats>>('/portal/stats/overview', {
        baseURL: useApiBase(),
      })
      return (
        res.data ?? {
          total_funds: 0,
          total_companies: 0,
          latest_nav_date: null,
          type_distribution: [],
        }
      )
    },
    { server: true },
  )
}

/** 区间收益分布 */
export function useReturnDistribution(period = '1y') {
  return useAsyncData<ReturnDistribution>(`return-dist-${period}`, async () => {
    const res = await $fetch<ApiResponse<ReturnDistribution>>('/portal/stats/return-distribution', {
      baseURL: useApiBase(),
      query: { period },
    })
    return res.data ?? { period, total: 0, buckets: [] }
  })
}

/** 单只基金详情 */
export function useFundDetail(code: string) {
  return useAsyncData<FundDetail | null>(`fund-detail-${code}`, async () => {
    const res = await $fetch<ApiResponse<FundDetail>>(`/portal/funds/${code}`, {
      baseURL: useApiBase(),
    })
    return res.data
  })
}

/** 区间指标 */
export function useFundMetrics(code: string) {
  return useAsyncData<FundMetric[]>(`fund-metrics-${code}`, async () => {
    const res = await $fetch<ApiResponse<FundMetric[]>>(`/portal/funds/${code}/metrics`, {
      baseURL: useApiBase(),
    })
    return res.data ?? []
  })
}

/**
 * 净值序列（图表用）。
 *
 * period 支持传 ref：切换区间时自动重新请求，SSR 阶段先取默认区间。
 * key 不含 period，避免每切一次就多一个缓存条目。
 */
export function useFundNavs(code: string, period: MaybeRef<NavRange> = '1y', limit = 800) {
  return useAsyncData<NavPoint[]>(
    `fund-navs-${code}`,
    async () => {
      const res = await $fetch<ApiResponse<NavPoint[]>>(`/portal/funds/${code}/navs`, {
        baseURL: useApiBase(),
        query: { period: unref(period), limit },
      })
      return res.data ?? []
    },
    { watch: [() => unref(period)] },
  )
}

/**
 * 季度重仓股。quarter 支持传 ref：切换季度时自动重新请求。
 * 债券 / 货币基金通常没有股票持仓，返回空列表属正常。
 */
export function useFundHoldings(code: string, quarter: MaybeRef<string | null> = null) {
  return useAsyncData<FundHoldingsResult>(
    `fund-holdings-${code}`,
    async () => {
      const res = await $fetch<ApiResponse<FundHoldingsResult>>(`/portal/funds/${code}/holdings`, {
        baseURL: useApiBase(),
        query: { quarter: unref(quarter) ?? undefined },
      })
      return res.data ?? { quarters: [], quarter: null, items: [], total_ratio: null }
    },
    { watch: [() => unref(quarter)] },
  )
}

/** Current stock quotes load separately so an upstream outage cannot hide quarterly holdings. */
export function useFundHoldingQuotes(code: string, quarter: MaybeRef<string | null> = null) {
  return useAsyncData<FundHoldingQuotesResult>(
    `fund-holding-quotes-${code}`,
    async () => {
      const res = await $fetch<ApiResponse<FundHoldingQuotesResult>>(
        `/portal/funds/${code}/holdings/quotes`,
        {
          baseURL: useApiBase(),
          query: { quarter: unref(quarter) ?? undefined },
        },
      )
      return res.data ?? { items: [], fetched_at: '' }
    },
    { server: false, lazy: true, watch: [() => unref(quarter)] },
  )
}
