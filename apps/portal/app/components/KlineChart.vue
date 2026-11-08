<script setup lang="ts">
/**
 * 指数 K 线图（蜡烛 + 成交量 + 均线）。
 *
 * 为什么这里不再手写 SVG：
 * 分时图的横轴是固定的 241 个点、纵轴以昨收对称，几何规则简单；
 * K 线却要缩放、平移、按十字光标读数、在几百根蜡烛之间保持性能，
 * 这些用 SVG 手写会变成一个小型图表库。lightweight-charts 压缩后约 45KB，
 * 只做行情图，正好覆盖需求。
 *
 * 库在 onMounted 里动态引入：SSR 阶段没有 DOM，也不需要把图表打进首屏包。
 */
import type { IndexCandlePoint } from '@project/shared'
import { fmtAmountCN, fmtPct } from '@project/shared'

const props = withDefaults(
  defineProps<{
    points: IndexCandlePoint[]
    /** day：日线；week：由日线聚合成周线 */
    period?: 'day' | 'week'
    height?: number
  }>(),
  { period: 'day', height: 380 },
)

const UP = '#dc2626'
const DOWN = '#059669'

interface Bar {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
}

const container = ref<HTMLElement | null>(null)
const legend = ref<{
  time: string
  open: number
  high: number
  low: number
  close: number
  amount: number
  pct: number | null
} | null>(null)

/** 把 "YYYY-MM-DD" 按 UTC 解析，避免本地时区把日期推前一天 */
function parseDate(value: string): Date {
  return new Date(`${value}T00:00:00Z`)
}

/**
 * 日线聚合成周线：按 ISO 周分组，开取首、收取末、高低取极值、量求和。
 * 日期用该周最后一个交易日，横轴才不会出现周末的空洞。
 */
function toWeekly(bars: Bar[]): Bar[] {
  const weeks: Bar[] = []
  let current: { key: string; bar: Bar } | null = null

  for (const bar of bars) {
    const day = parseDate(bar.time)
    const monday = new Date(day)
    const weekday = (day.getUTCDay() + 6) % 7 // 周一 = 0
    monday.setUTCDate(day.getUTCDate() - weekday)
    const key = monday.toISOString().slice(0, 10)

    if (!current || current.key !== key) {
      if (current) weeks.push(current.bar)
      current = { key, bar: { ...bar } }
      continue
    }

    current.bar.high = Math.max(current.bar.high, bar.high)
    current.bar.low = Math.min(current.bar.low, bar.low)
    current.bar.close = bar.close
    current.bar.volume += bar.volume
    current.bar.amount += bar.amount
    current.bar.time = bar.time
  }

  if (current) weeks.push(current.bar)
  return weeks
}

const bars = computed<Bar[]>(() => {
  const daily = props.points
    .filter((p) => Number.isFinite(p.close))
    .map((p) => ({
      time: p.trade_date,
      open: p.open,
      high: p.high,
      low: p.low,
      close: p.close,
      volume: p.volume ?? 0,
      amount: p.amount ?? 0,
    }))
    .sort((a, b) => a.time.localeCompare(b.time))

  return props.period === 'week' ? toWeekly(daily) : daily
})

const byTime = computed(() => {
  const map = new Map<string, Bar>()
  for (const bar of bars.value) map.set(bar.time, bar)
  return map
})

/** 均线：窗口内收盘价简单平均，前 n-1 个点没有值就不画 */
const MA_WINDOWS = [5, 10, 20, 60] as const
const MA_COLORS: Record<number, string> = {
  5: '#d97706',
  10: '#2563eb',
  20: '#7c3aed',
  60: '#0f766e',
}

function movingAverage(source: Bar[], window: number) {
  const result: { time: string; value: number }[] = []
  let sum = 0
  source.forEach((bar, index) => {
    sum += bar.close
    const leaving = source[index - window]
    if (leaving) sum -= leaving.close
    if (index >= window - 1) {
      result.push({ time: bar.time, value: sum / window })
    }
  })
  return result
}

const maValues = computed(() => {
  const source = bars.value
  return MA_WINDOWS.map((window) => {
    const series = movingAverage(source, window)
    const last = series[series.length - 1]
    return { window, color: MA_COLORS[window], value: last?.value ?? null }
  })
})

/** 悬停读数：默认显示最后一根 */
function describe(bar: Bar | undefined) {
  if (!bar) return null
  const index = bars.value.findIndex((item) => item.time === bar.time)
  const previous = index > 0 ? bars.value[index - 1] : undefined
  const pct =
    previous && previous.close ? ((bar.close - previous.close) / previous.close) * 100 : null
  return {
    time: bar.time,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    amount: bar.amount,
    pct,
  }
}

let chart: import('lightweight-charts').IChartApi | null = null
let candlesApi: import('lightweight-charts').ISeriesApi<'Candlestick'> | null = null
let volumeApi: import('lightweight-charts').ISeriesApi<'Histogram'> | null = null
let maApis: import('lightweight-charts').ISeriesApi<'Line'>[] = []
let observer: ResizeObserver | null = null

/** 数据变化时重画（日线/周线切换），不重建图表实例 */
function render() {
  if (!chart || !candlesApi || !volumeApi) return
  const source = bars.value
  if (!source.length) return

  candlesApi.setData(
    source.map((bar) => ({
      time: bar.time,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    })),
  )
  volumeApi.setData(
    source.map((bar) => ({
      time: bar.time,
      value: bar.volume,
      color: bar.close >= bar.open ? `${UP}55` : `${DOWN}55`,
    })),
  )
  MA_WINDOWS.forEach((window, index) => {
    const api = maApis[index]
    api?.setData(movingAverage(source, window))
  })

  // 默认只看最近 120 根，剩下的让用户自己缩放——全量塞进屏幕会挤成一条线
  const visible = Math.min(120, source.length)
  chart.timeScale().setVisibleLogicalRange({
    from: source.length - visible - 0.5,
    to: source.length + 2,
  })
  legend.value = describe(source[source.length - 1])
}

onMounted(async () => {
  const element = container.value
  if (!element) return

  const { CandlestickSeries, HistogramSeries, LineSeries, ColorType, CrosshairMode, createChart } =
    await import('lightweight-charts')

  const api = createChart(element, {
    width: element.clientWidth,
    height: props.height,
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: '#64748b',
      fontFamily: "'SF Mono', 'DIN Alternate', ui-monospace, SFMono-Regular, Menlo, monospace",
      attributionLogo: true,
    },
    grid: {
      vertLines: { color: '#f1f5f9' },
      horzLines: { color: '#f1f5f9' },
    },
    rightPriceScale: {
      borderColor: '#e2e8f0',
      // 底部留出 22% 给成交量，避免量柱压在蜡烛上
      scaleMargins: { top: 0.08, bottom: 0.22 },
    },
    timeScale: {
      borderColor: '#e2e8f0',
      rightOffset: 3,
      barSpacing: 7,
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: { color: '#94a3b8', width: 1, style: 3, labelBackgroundColor: '#475569' },
      horzLine: { color: '#94a3b8', width: 1, style: 3, labelBackgroundColor: '#475569' },
    },
    handleScroll: {
      mouseWheel: false,
      pressedMouseMove: true,
      horzTouchDrag: true,
      vertTouchDrag: false,
    },
    handleScale: { mouseWheel: false, pinch: true, axisPressedMouseMove: true },
    localization: {
      locale: 'zh-CN',
      priceFormatter: (price: number) => price.toFixed(2),
    },
  })
  chart = api

  candlesApi = api.addSeries(CandlestickSeries, {
    upColor: UP,
    downColor: DOWN,
    borderUpColor: UP,
    borderDownColor: DOWN,
    wickUpColor: UP,
    wickDownColor: DOWN,
    priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    // 右侧已经有最新价标签，再画一条虚线只会干扰视线
    priceLineVisible: false,
  })

  volumeApi = api.addSeries(HistogramSeries, {
    priceScaleId: 'volume',
    priceFormat: { type: 'volume' },
    priceLineVisible: false,
    lastValueVisible: false,
  })
  // 成交量单独一条价格轴，压在底部 22% 的区域
  volumeApi.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })

  maApis = MA_WINDOWS.map((window) =>
    api.addSeries(LineSeries, {
      color: MA_COLORS[window],
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    }),
  )

  render()

  api.subscribeCrosshairMove((param) => {
    if (!param.time || param.point === undefined) {
      legend.value = describe(bars.value[bars.value.length - 1])
      return
    }
    legend.value = describe(byTime.value.get(String(param.time)))
  })

  observer = new ResizeObserver((entries) => {
    const entry = entries[0]
    if (entry && chart) chart.applyOptions({ width: Math.floor(entry.contentRect.width) })
  })
  observer.observe(element)
})

/** 日线 / 周线切换：同一实例换数据，避免整块重建 */
watch(bars, () => render())

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
  chart?.remove()
  chart = null
})
</script>

<template>
  <div class="kline">
    <div class="kline__meta">
      <span v-if="legend" class="kline__date num">{{ legend.time }}</span>
      <span v-if="legend" class="kline__ohlc">
        <span
          >开 <b class="num">{{ legend.open.toFixed(2) }}</b></span
        >
        <span
          >高 <b class="num up">{{ legend.high.toFixed(2) }}</b></span
        >
        <span
          >低 <b class="num down">{{ legend.low.toFixed(2) }}</b></span
        >
        <span
          >收 <b class="num">{{ legend.close.toFixed(2) }}</b></span
        >
        <span :class="(legend.pct ?? 0) >= 0 ? 'up' : 'down'" class="num">
          {{ fmtPct(legend.pct) }}
        </span>
        <span
          >额 <b class="num">{{ fmtAmountCN(legend.amount) }}</b></span
        >
      </span>

      <span class="kline__ma">
        <span v-for="ma in maValues" :key="ma.window" :style="{ color: ma.color }">
          MA{{ ma.window }} <b class="num">{{ ma.value == null ? '—' : ma.value.toFixed(2) }}</b>
        </span>
      </span>
    </div>

    <div ref="container" class="kline__canvas" :style="{ height: `${height}px` }" />

    <div v-if="!bars.length" class="kline__empty">
      <p>K 线数据暂不可用</p>
      <span>行情源没有返回该指数的日线数据，稍后再看。</span>
    </div>
  </div>
</template>

<style scoped>
.kline {
  position: relative;
}

.kline__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: center;
  margin-bottom: 6px;
  font-size: 11.5px;
  color: var(--muted);
}

.kline__date {
  font-weight: 600;
  color: var(--ink-2);
}

.kline__ohlc,
.kline__ma {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.kline__ohlc b {
  font-weight: 600;
  color: var(--ink-2);
}

.kline__ohlc .up b,
.kline__ohlc .up {
  color: var(--up);
}

.kline__ohlc .down b,
.kline__ohlc .down {
  color: var(--down);
}

.kline__canvas {
  width: 100%;
}

.kline__empty {
  position: absolute;
  inset: 26px 0 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  background: var(--bg-soft);
  border: 1px dashed var(--line);
  border-radius: var(--radius-sm);
}

.kline__empty p {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-2);
}

.kline__empty span {
  font-size: 12px;
}
</style>
