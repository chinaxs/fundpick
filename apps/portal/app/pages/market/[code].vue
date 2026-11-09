<script setup lang="ts">
/**
 * 单指数详情：实时点位 + 今日分时。
 *
 * 头部点位优先取 SSE 推送的共享快照（5 秒一更），
 * 没有推送时退回页面自己请求的单指数接口，保证直链进来也有数据。
 * 分时图走独立轮询（盘中 20 秒），因为它是一天里逐步新增的点。
 */
import { fmtAmountCN, fmtPct, fmtPoint, toneOf } from '@project/shared'

// 指数之间用 chip 互跳，路由参数变化时强制重建页面，避免拿到上一个指数的数据
definePageMeta({
  // 只按指数代码重建：切页签会改 query，用 fullPath 会导致整页重挂载
  key: (route) => String(route.params.code),
})

const route = useRoute()
const router = useRouter()
const code = String(route.params.code)

const { data: detail, error: detailError } = await useIndexDetail(code)
if (detailError.value?.statusCode === 404) {
  throw createError({ statusCode: 404, statusMessage: '该指数不在跟踪清单内', fatal: true })
}

const { data: intraday, refresh: refreshIntraday } = await useIndexIntraday(code)
const { data: market } = useMarketIndices()

/** 分时 / 日K / 周K：K 线按需加载，切过去才发请求 */
/** 初始页签可来自链接（?tab=day），方便直接分享到 K 线 */
const initialTab = () => {
  const value = String(route.query.tab ?? '')
  return value === 'day' || value === 'week' ? value : 'intraday'
}
const tab = ref<'intraday' | 'day' | 'week'>(initialTab())
const TABS = [
  { value: 'intraday', label: '分时' },
  { value: 'day', label: '日K' },
  { value: 'week', label: '周K' },
] as const

const {
  data: candles,
  error: candlesError,
  refresh: loadCandles,
  status: candlesStatus,
} = useIndexCandles(code)

watch(tab, (value) => {
  if (value !== 'intraday' && candlesStatus.value === 'idle') loadCandles()
  router.replace({
    query: { ...route.query, tab: value === 'intraday' ? undefined : value },
  })
})

const live = computed(
  () => market.value?.items.find((item) => item.code === code) ?? detail.value ?? null,
)

const isTrading = computed(() => market.value?.market_status === 'trading')
const tone = computed(() => toneOf(live.value?.change_pct))

const siblings = computed(() => market.value?.items ?? [])

const stats = computed(() => {
  const q = live.value
  return [
    { label: '今开', value: fmtPoint(q?.open), tone: '' },
    { label: '昨收', value: fmtPoint(q?.prev_close), tone: '' },
    { label: '最高', value: fmtPoint(q?.high), tone: 'up' },
    { label: '最低', value: fmtPoint(q?.low), tone: 'down' },
    {
      label: '振幅',
      value: q?.amplitude == null ? '—' : `${q.amplitude.toFixed(2)}%`,
      tone: '',
    },
    { label: '成交额', value: fmtAmountCN(q?.amount), tone: '' },
  ]
})

/**
 * 三个时间必须分开显示：
 * - data_as_of 是**原始行情时间**（快照上游没有时间戳时为空）；
 * - fetched_at 是最近一次抓取时间；
 * - as_of 只是本次响应时间，不能当成"行情刚更新"。
 */
function clockOf(iso?: string | null, withDate = false) {
  if (!iso) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    ...(withDate ? { month: '2-digit', day: '2-digit' } : {}),
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(iso))
}

const panel = computed(() => (tab.value === 'intraday' ? intraday.value : candles.value))

const quoteDate = computed(
  () => intraday.value?.trade_date ?? lastBarDate.value ?? market.value?.trade_date ?? null,
)

const quoteTimeLabel = computed(() => {
  const dataTime = panel.value?.data_as_of ?? market.value?.data_as_of
  if (dataTime) {
    return `行情时间 ${clockOf(dataTime, tab.value !== 'intraday')}`
  }
  const fetched = panel.value?.fetched_at ?? market.value?.fetched_at
  return fetched ? `抓取于 ${clockOf(fetched)}` : ''
})

const degraded = computed(() => Boolean(panel.value?.degraded ?? market.value?.degraded))
const degradedReason = computed(
  () => panel.value?.degraded_reason ?? market.value?.degraded_reason ?? '上游行情暂时不可用',
)
const calendarUnknown = computed(
  () => panel.value?.calendar_known === false || market.value?.calendar_known === false,
)

/** 分时最新一个点的时间（带日期）：跨日或休市时只看 HH:MM 会误判成今天 */
const lastPointTime = computed(() => clockOf(intraday.value?.data_as_of, true))
const lastBarDate = computed(() => {
  const points = candles.value?.points ?? []
  const last = points[points.length - 1]
  return last ? String(last.trade_date) : ''
})

const statusLabel = computed(
  () => market.value?.status_label || intraday.value?.status_label || '行情加载中',
)

/** 分时刷新：交易时段 20 秒，休市后 120 秒（服务端也是这个节奏） */
let timer: ReturnType<typeof setTimeout> | undefined

async function pollIntraday() {
  // 切到 K 线页签时不再刷分时：看不见的数据没必要请求
  if (tab.value === 'intraday') await refreshIntraday()
  schedule()
}

function schedule() {
  const seconds = intraday.value?.refresh_seconds ?? 60
  timer = setTimeout(pollIntraday, seconds * 1000)
}

onMounted(() => {
  schedule()
  if (tab.value !== 'intraday') loadCandles()
})
onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})

const indexName = computed(() => live.value?.name ?? intraday.value?.name ?? code)

useSeoMeta({
  title: `${indexName.value} 实时行情与今日分时走势`,
  description: `${indexName.value}（${code}）的最新点位、涨跌幅、今开昨收、成交额与当日分时走势，数据来自公开行情源，延迟约数秒到十几秒。`,
})
</script>

<template>
  <div class="detail">
    <section class="detail__head">
      <div class="container">
        <NuxtLink to="/market" class="back">← 大盘</NuxtLink>

        <div class="head">
          <div class="head__main">
            <div class="head__title">
              <h1 class="name">{{ indexName }}</h1>
              <span class="code num">{{ code }}</span>
              <span v-if="live?.group" class="group">{{ live.group }}</span>
            </div>

            <div class="head__quote" :class="tone">
              <span class="price num">{{ fmtPoint(live?.price) }}</span>
              <span class="delta num">{{ fmtPoint(live?.change) }}</span>
              <span class="pct num">{{ fmtPct(live?.change_pct) }}</span>
            </div>

            <p class="head__meta">
              <span class="state" :class="{ 'is-live': isTrading }">
                <i class="state__dot" />
                {{ statusLabel }}
              </span>
              <span v-if="quoteDate">行情日期 {{ quoteDate }}</span>
              <span v-if="quoteTimeLabel">{{ quoteTimeLabel }}</span>
              <span v-if="degraded" class="stale" :title="degradedReason">数据延迟</span>
              <span
                v-if="calendarUnknown"
                class="stale"
                title="交易日历未覆盖当前年份，交易状态按星期估算"
                >日历未覆盖</span
              >
              <span v-if="isTrading && market?.push_seconds">
                每 {{ market.push_seconds }} 秒推送
              </span>
            </p>
          </div>

          <dl class="head__stats">
            <div v-for="item in stats" :key="item.label">
              <dt>{{ item.label }}</dt>
              <dd class="num" :class="item.tone">{{ item.value }}</dd>
            </div>
          </dl>
        </div>

        <nav class="switch" aria-label="切换指数">
          <NuxtLink
            v-for="item in siblings"
            :key="item.code"
            :to="`/market/${item.code}`"
            class="switch__item"
            :class="{ 'is-active': item.code === code }"
          >
            <span class="switch__name">{{ item.name }}</span>
            <span class="switch__pct num" :class="toneOf(item.change_pct)">
              {{ fmtPct(item.change_pct) }}
            </span>
          </NuxtLink>
        </nav>
      </div>
    </section>

    <section class="container detail__body">
      <div class="panel">
        <header class="panel__head">
          <div>
            <div class="tabs">
              <button
                v-for="item in TABS"
                :key="item.value"
                type="button"
                class="tabs__btn"
                :class="{ 'is-active': tab === item.value }"
                @click="tab = item.value"
              >
                {{ item.label }}
              </button>
            </div>
            <p class="panel__sub">
              <template v-if="tab === 'intraday'">
                <template v-if="intraday?.trade_date">
                  {{ intraday.trade_date }} · 每分钟一个点
                </template>
                <template v-else>分钟级走势</template>
                <template v-if="intraday?.prev_close">
                  · 昨收 <span class="num">{{ fmtPoint(intraday.prev_close) }}</span>
                </template>
                <template v-if="lastPointTime">· 最新点 {{ lastPointTime }}</template>
              </template>
              <template v-else>
                {{ tab === 'week' ? '周线' : '日线' }} · 近 3 年 · 可拖动缩放
                <template v-if="lastBarDate">· 最后一根 {{ lastBarDate }}</template>
              </template>
              <template v-if="degraded && degradedReason">
                · <span class="stale-inline">{{ degradedReason }}</span>
              </template>
            </p>
          </div>

          <div v-if="tab === 'intraday'" class="legend">
            <span class="legend__item"><i class="legend__line legend__line--price" />价格</span>
            <span class="legend__item"><i class="legend__line legend__line--avg" />均价</span>
            <span class="legend__item"><i class="legend__line legend__line--base" />昨收</span>
          </div>
        </header>

        <IntradayChart
          v-if="tab === 'intraday'"
          :points="intraday?.points ?? []"
          :prev-close="intraday?.prev_close ?? null"
          :height="326"
        />

        <template v-else>
          <p v-if="candlesError" class="panel__state">
            K 线暂不可用，行情源可能正在波动。
            <button type="button" class="panel__retry" @click="loadCandles()">重试</button>
          </p>
          <p v-else-if="candlesStatus !== 'success'" class="panel__state">K 线加载中…</p>
          <KlineChart
            v-else
            :points="candles?.points ?? []"
            :period="tab === 'week' ? 'week' : 'day'"
            :height="380"
          />
        </template>
      </div>

      <div class="notes">
        <template v-if="tab === 'intraday'">
          <p class="notes__item">
            <strong>怎么看：</strong>价格线在昨收上方为涨（红）、下方为跌（绿）；
            黄线是当日累计成交均价，价格长期低于均价说明盘中卖压偏重。
          </p>
          <p class="notes__item">
            <strong>数据口径：</strong>分钟级点位来自东方财富公开行情，盘中延迟约数秒到十几秒，
            不构成逐笔成交。非交易时段展示最近一个交易日的完整分时。
          </p>
        </template>
        <template v-else>
          <p class="notes__item">
            <strong>怎么看：</strong>红涨绿跌；下方柱子是成交量，四条线是 MA5 / 10 / 20 / 60
            收盘均价。按住拖动可平移，捏合或拖时间轴可缩放。
          </p>
          <p class="notes__item">
            <strong>数据口径：</strong>日线来自东方财富公开行情，指数无分红除权，不需要复权处理；
            周线由日线聚合而成（开盘取周一、收盘取周五、最高最低取区间极值、成交量求和）。
          </p>
        </template>
      </div>

      <p class="footnote">
        指数本身不可直接投资，可通过跟踪该指数的指数基金参与。数据仅作研究参考，不构成投资建议。
      </p>
    </section>
  </div>
</template>

<style scoped>
.detail__head {
  background: linear-gradient(180deg, var(--bg-soft) 0%, var(--bg) 100%);
  border-bottom: 1px solid var(--line-soft);
}

.back {
  display: inline-block;
  padding-top: 24px;
  font-size: 12.5px;
  color: var(--muted);
}

.back:hover {
  color: var(--brand);
}

.head {
  display: flex;
  flex-wrap: wrap;
  gap: 28px;
  align-items: flex-end;
  justify-content: space-between;
  padding: 14px 0 22px;
}

.head__title {
  display: flex;
  gap: 10px;
  align-items: center;
}

.name {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.code {
  padding: 2px 7px;
  font-family: var(--font-num);
  font-size: 11.5px;
  color: var(--muted);
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 6px;
}

.group {
  font-size: 11.5px;
  color: var(--muted-2);
}

.head__quote {
  display: flex;
  gap: 12px;
  align-items: baseline;
  margin-top: 8px;
  color: var(--ink);
}

.head__quote.up {
  color: var(--up);
}

.head__quote.down {
  color: var(--down);
}

.price {
  font-size: 40px;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.02em;
}

.delta {
  font-size: 15px;
  font-weight: 600;
}

.pct {
  font-size: 16px;
  font-weight: 600;
}

.head__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--muted-2);
}

.state {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  font-weight: 600;
  color: var(--ink-2);
}

.state__dot {
  width: 6px;
  height: 6px;
  background: var(--muted-2);
  border-radius: 50%;
}

.state.is-live {
  color: var(--up);
}

.state.is-live .state__dot {
  background: var(--up);
  animation: live 1.8s ease-in-out infinite;
}

@keyframes live {
  50% {
    opacity: 0.3;
  }
}

.head__stats {
  display: grid;
  grid-template-columns: repeat(6, minmax(64px, auto));
  gap: 4px 22px;
  margin: 0;
  padding: 12px 16px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-xs);
}

.head__stats dt {
  font-size: 10.5px;
  color: var(--muted-2);
}

.head__stats dd {
  margin: 1px 0 0;
  font-size: 13px;
  color: var(--ink-2);
}

.head__stats dd.up {
  color: var(--up);
}

.head__stats dd.down {
  color: var(--down);
}

.switch {
  display: flex;
  gap: 6px;
  padding-bottom: 16px;
  overflow-x: auto;
  scrollbar-width: none;
}

.switch::-webkit-scrollbar {
  display: none;
}

.switch__item {
  display: flex;
  flex: none;
  gap: 7px;
  align-items: baseline;
  padding: 5px 11px;
  font-size: 12.5px;
  color: var(--ink-2);
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 999px;
  transition:
    border-color 0.15s ease,
    color 0.15s ease;
}

.switch__item:hover {
  border-color: var(--muted-2);
}

.switch__item.is-active {
  color: var(--brand);
  background: var(--brand-soft);
  border-color: transparent;
}

.switch__pct.up {
  color: var(--up);
}

.switch__pct.down {
  color: var(--down);
}

.detail__body {
  padding-top: 26px;
  padding-bottom: 64px;
}

.panel {
  padding: 20px 20px 12px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-xs);
}

.panel__head {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
}

.tabs {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: 999px;
}

.tabs__btn {
  padding: 5px 16px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--muted);
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 999px;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.tabs__btn.is-active {
  color: var(--ink);
  background: var(--bg);
  box-shadow: var(--shadow-xs);
}

.panel__state {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
  height: 326px;
  margin: 0;
  font-size: 13px;
  color: var(--muted);
  background: var(--bg-soft);
  border: 1px dashed var(--line);
  border-radius: var(--radius-sm);
}

.panel__retry {
  padding: 3px 12px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--brand);
  cursor: pointer;
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 999px;
}

.panel__sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--muted-2);
}

.legend {
  display: flex;
  gap: 14px;
  align-items: center;
  font-size: 11.5px;
  color: var(--muted);
}

.legend__item {
  display: inline-flex;
  gap: 5px;
  align-items: center;
}

.legend__line {
  width: 14px;
  height: 2px;
  border-radius: 2px;
}

.legend__line--price {
  background: var(--up);
}

.legend__line--avg {
  background: #d97706;
}

.legend__line--base {
  height: 1px;
  background: repeating-linear-gradient(90deg, var(--muted-2) 0 3px, transparent 3px 6px);
}

.notes {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.notes__item {
  margin: 0;
  padding: 14px 16px;
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--muted);
  background: var(--bg-soft);
  border-radius: var(--radius-sm);
}

.notes__item strong {
  font-weight: 600;
  color: var(--ink-2);
}

.footnote {
  margin: 18px 0 0;
  font-size: 11.5px;
  line-height: 1.9;
  color: var(--muted-2);
}

@media (max-width: 900px) {
  .head__stats {
    grid-template-columns: repeat(3, minmax(64px, auto));
    width: 100%;
  }
}

@media (max-width: 640px) {
  .head {
    gap: 18px;
    padding-top: 10px;
  }

  .name {
    font-size: 22px;
  }

  .price {
    font-size: 32px;
  }

  .notes {
    grid-template-columns: 1fr;
  }

  .panel {
    padding: 16px 12px 8px;
  }
}
</style>
