/**
 * 基金数据获取：与 usePortalApi 保持同一套约定（useAsyncData + 显式泛型）。
 */
import type { MaybeRef } from 'vue'
import type {
  ApiResponse,
  FilterOptions,
  OverviewStats,
  ReturnDistribution,
  FundDetail,
  FundListItem,
  FundMetric,
  FundQuery,
  NavPoint,
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
      return res.data ?? { types: [], risk_levels: [], companies: [], periods: [], sort_fields: [] }
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

/** 净值序列（图表用） */
export function useFundNavs(code: string, limit = 500) {
  return useAsyncData<NavPoint[]>(`fund-navs-${code}-${limit}`, async () => {
    const res = await $fetch<ApiResponse<NavPoint[]>>(`/portal/funds/${code}/navs`, {
      baseURL: useApiBase(),
      query: { limit },
    })
    return res.data ?? []
  })
}
