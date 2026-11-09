/**
 * 市场指数行情：与 useFundApi 同一套约定（useAsyncData + 显式泛型）。
 *
 * 首屏能拿到什么：SSR 阶段服务端请求一次，客户端接管后复用同一份 payload；
 * 之后由 SSE 推送更新（`useMarketStream`），推送不可用时自动退回轮询。
 */
import type { MaybeRef } from 'vue'
import type {
  ApiResponse,
  IndexCandlesData,
  IndexIntradayData,
  IndexQuote,
  IndexTrendsData,
  MarketIndicesData,
} from '@project/shared'
import { useApiBase } from './usePortalApi'

export const EMPTY_MARKET: MarketIndicesData = {
  items: [],
  market_status: 'closed',
  status_label: '',
  trade_date: null,
  as_of: '',
  source: '',
  refresh_seconds: 15,
  push_seconds: 5,
}

/** 核心指数实时快照（8 个，服务端已过滤并排序） */
export function useMarketIndices() {
  return useAsyncData<MarketIndicesData>(
    'market-indices',
    async () => {
      const res = await $fetch<ApiResponse<MarketIndicesData>>('/portal/market/indices', {
        baseURL: useApiBase(),
      })
      return res.data ?? EMPTY_MARKET
    },
    { default: () => EMPTY_MARKET, server: true },
  )
}

/** 指数日线走势（迷你图用）；日线一天一变，不必轮询。days 支持 ref，切换区间自动重取 */
export function useIndexTrends(days: MaybeRef<number> = 60) {
  return useAsyncData<IndexTrendsData>(
    'index-trends',
    async () => {
      const span = unref(days)
      const res = await $fetch<ApiResponse<IndexTrendsData>>('/portal/market/indices/trends', {
        baseURL: useApiBase(),
        query: { days: span },
      })
      return res.data ?? { days: span, items: [], as_of: '' }
    },
    {
      default: () => ({ days: unref(days), items: [], as_of: '' }),
      server: true,
      watch: [() => unref(days)],
    },
  )
}

/** 单个指数快照（详情页首屏；之后由 SSE 推送覆盖） */
export function useIndexDetail(code: string) {
  return useAsyncData<IndexQuote | null>(
    `market-index-${code}`,
    async () => {
      const res = await $fetch<ApiResponse<IndexQuote>>(`/portal/market/indices/${code}`, {
        baseURL: useApiBase(),
      })
      return res.data ?? null
    },
    { default: () => null },
  )
}

const EMPTY_INTRADAY = (code: string): IndexIntradayData => ({
  code,
  name: '',
  prev_close: null,
  points: [],
  trade_date: null,
  market_status: 'closed',
  status_label: '',
  as_of: '',
  source: '',
  refresh_seconds: 60,
})

/** 当日分时；分时一天只加一个点，用轮询足够，不值得再占一条连接 */
export function useIndexIntraday(code: string) {
  return useAsyncData<IndexIntradayData>(
    `market-intraday-${code}`,
    async () => {
      const res = await $fetch<ApiResponse<IndexIntradayData>>(
        `/portal/market/indices/${code}/intraday`,
        { baseURL: useApiBase() },
      )
      return res.data ?? EMPTY_INTRADAY(code)
    },
    { default: () => EMPTY_INTRADAY(code), server: true },
  )
}

const EMPTY_CANDLES = (code: string): IndexCandlesData => ({
  code,
  name: '',
  days: 0,
  points: [],
  as_of: '',
  source: '',
})

/**
 * 日 K 序列。默认不请求（immediate: false）：
 * 详情页首屏是分时，K 线等用户切页签再拉，避免白花一次上游请求。
 */
export function useIndexCandles(code: string, days = 750) {
  return useAsyncData<IndexCandlesData>(
    `market-candles-${code}-${days}`,
    async () => {
      const res = await $fetch<ApiResponse<IndexCandlesData>>(
        `/portal/market/indices/${code}/candles`,
        { baseURL: useApiBase(), query: { days } },
      )
      return res.data ?? EMPTY_CANDLES(code)
    },
    { default: () => EMPTY_CANDLES(code), server: false, immediate: false },
  )
}

export type StreamStatus = 'connecting' | 'live' | 'polling'

/** 推送连接状态（只读）：布局里建立连接，组件用它显示"推送/轮询" */
export function useMarketStreamStatus() {
  return useState<StreamStatus>('market-stream-status', () => 'connecting')
}

/**
 * 订阅行情推送（SSE），把每一帧写回 `useMarketIndices` 的共享状态。
 *
 * 只在布局里调用一次：所有调用 `useMarketIndices()` 的组件拿的是同一份 ref，
 * 因此自动跟着更新。多次调用会建立多条连接，务必不要散落在各页面里。
 *
 * 降级策略：EventSource 本身会自动重连，但如果反向代理把流缓冲了，
 * 浏览器会一直"连着但收不到帧"——所以加一个看门狗，
 * 超过 45 秒没有帧就切换到轮询，收到帧再切回来。
 */
export function useMarketStream() {
  const { data, refresh } = useMarketIndices()
  const status = useMarketStreamStatus()

  let source: EventSource | null = null
  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let watchdog: ReturnType<typeof setInterval> | null = null
  let lastFrameAt = 0
  let disposed = false

  function stopPolling() {
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  function startPolling() {
    if (pollTimer) return
    status.value = 'polling'

    const tick = async () => {
      await refresh()
      if (!disposed) pollTimer = setTimeout(tick, 15000)
    }
    void tick()
  }

  function connect() {
    source = new EventSource(`${useApiBase()}/portal/market/indices/stream`)
    lastFrameAt = Date.now()

    source.addEventListener('quotes', (event) => {
      lastFrameAt = Date.now()
      status.value = 'live'
      stopPolling()

      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as MarketIndicesData
        // 上游故障时服务端会推空列表，此时保留上一次的数据，不把页面清空
        if (payload.items?.length) data.value = payload
      } catch {
        // 单帧解析失败不影响后续帧
      }
    })

    source.onopen = () => {
      status.value = 'live'
    }

    // 不在这里 close()：浏览器自带的自动重连比手写策略更可靠。
    // 真正连不上时由看门狗接管轮询。
    source.onerror = () => {
      if (!pollTimer) status.value = 'polling'
    }
  }

  onMounted(() => {
    connect()
    watchdog = setInterval(() => {
      if (lastFrameAt && Date.now() - lastFrameAt > 45_000) startPolling()
    }, 10_000)
  })

  onBeforeUnmount(() => {
    disposed = true
    source?.close()
    source = null
    stopPolling()
    if (watchdog) clearInterval(watchdog)
  })

  return { status }
}
