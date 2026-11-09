import type {
  FundPeriod,
  FundQuery,
  FundSortBy,
  FundType,
  FundSector,
  RiskLevel,
} from '@project/shared'
import {
  FUND_PERIOD_MAP,
  FUND_TYPE_MAP,
  FUND_SECTOR_MAP,
  RISK_LEVEL_MAP,
  FUND_SORT_MAP,
} from '@project/shared'

/** URL 是筛选条件的唯一来源；浏览器返回、分享链接与刷新保持一致。 */
export function useFundScreener() {
  const route = useRoute()
  const router = useRouter()
  function value(key: string): string {
    const item = route.query[key]
    return typeof item === 'string' ? item : ''
  }
  function option<T extends string>(key: string, options: Record<T, string>): T | undefined {
    const item = value(key)
    return Object.hasOwn(options, item) ? (item as T) : undefined
  }
  function positiveInteger(key: string, fallback: number): number {
    const number = Number(value(key))
    return Number.isSafeInteger(number) && number > 0 && number <= 2147483647 ? number : fallback
  }
  const state = computed(() => ({
    keyword: value('keyword').trim(),
    type: option('type', FUND_TYPE_MAP),
    sector: option('sector', FUND_SECTOR_MAP),
    risk_level: option('risk_level', RISK_LEVEL_MAP),
    company_id: positiveInteger('company_id', 0) || undefined,
    period: option('period', FUND_PERIOD_MAP) ?? '1y',
    sort_by: option('sort_by', FUND_SORT_MAP) ?? 'return',
    sort_order: value('sort_order') === 'asc' ? ('asc' as const) : ('desc' as const),
    page: positiveInteger('page', 1),
    page_size: 20,
  }))
  const keyword = ref(state.value.keyword)
  const composing = ref(false)
  let timer: ReturnType<typeof setTimeout> | undefined

  function update(patch: FundQuery, replace = false) {
    clearTimeout(timer)
    const next = { ...state.value, page: 1, ...patch }
    const query: Record<string, string> = {}
    for (const [key, item] of Object.entries(next)) {
      if (
        item !== undefined &&
        item !== '' &&
        key !== 'page_size' &&
        !(key === 'page' && item === 1)
      ) {
        query[key] = String(item)
      }
    }
    return replace ? router.replace({ query }) : router.push({ query })
  }
  function applyKeyword() {
    clearTimeout(timer)
    if (composing.value || keyword.value.trim() === state.value.keyword) return
    return update({ keyword: keyword.value.trim() }, true)
  }
  watch(keyword, () => {
    clearTimeout(timer)
    if (!composing.value) timer = setTimeout(applyKeyword, 300)
  })
  watch(
    () => state.value.keyword,
    (text) => {
      clearTimeout(timer)
      keyword.value = text
    },
  )
  function reset() {
    clearTimeout(timer)
    keyword.value = ''
    return router.push({ query: {} })
  }
  function sort(field: FundSortBy) {
    const sort_order =
      state.value.sort_by === field
        ? state.value.sort_order === 'asc'
          ? 'desc'
          : 'asc'
        : ['max_drawdown', 'volatility'].includes(field)
          ? 'asc'
          : 'desc'
    return update({ sort_by: field, sort_order })
  }
  function setPeriod(period: string) {
    return update({ period: period as FundPeriod })
  }
  function toggleFilter(key: 'type' | 'sector' | 'risk_level', item?: string) {
    return update({ [key]: state.value[key] === item ? undefined : item } as {
      type?: FundType
      sector?: FundSector
      risk_level?: RiskLevel
    })
  }
  onBeforeUnmount(() => clearTimeout(timer))
  return { state, keyword, composing, update, applyKeyword, reset, sort, setPeriod, toggleFilter }
}
