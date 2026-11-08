<script setup lang="ts">
/**
 * 全站指数条：紧贴导航下方的一行行情。
 *
 * 为什么放在布局里而不是首页：用户在任何页面都想顺手看一下大盘，
 * 但这里只是"环境提示"，所以只给点位与涨跌幅，详细信息留给 /market。
 *
 * 这里也是全站唯一的行情订阅点：SSE 连一条，所有页面共用同一份数据。
 * 推不进来时自动退回轮询（见 useMarketStream），页面不会因此不更新。
 */
import { fmtPct, fmtPoint, toneOf, type IndexQuote } from '@project/shared'

/**
 * 指数条只放 6 个：8 个在 1200 容器里放不下，硬塞会把最后一个截断。
 * 想看全 8 个去 /market。
 */
const TICKER_CODES = ['000001', '399001', '399006', '000300', '000905', '899050']

const { data } = useMarketIndices()
const streamStatus = useMarketStreamStatus()

const items = computed(() => {
  const all = data.value?.items ?? []
  return TICKER_CODES.map((code) => all.find((item) => item.code === code)).filter(
    (item): item is IndexQuote => item !== undefined,
  )
})
const isTrading = computed(() => data.value?.market_status === 'trading')

/**
 * 优先显示原始行情时间；上游快照没有时间戳时退到"抓取时间"并标明，
 * 绝不把抓取时间写成行情时间。
 */
const timeText = computed(() => {
  const source = data.value?.data_as_of
  const fetched = data.value?.fetched_at
  const iso = source ?? fetched
  if (!iso) return ''
  const clock = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(iso))
  return source ? clock : `抓取 ${clock}`
})

const calendarUnknown = computed(() => data.value?.calendar_known === false)

/** 上游失败或缓存偏旧时给出明确提示，避免把旧点位当现价 */
const staleness = computed(() => {
  const age = data.value?.cache_age_seconds
  if (data.value?.degraded) {
    return age && age >= 60 ? `延迟 ${Math.round(age / 60)} 分钟` : '数据延迟'
  }
  if (typeof age === 'number' && age >= 120) return `缓存 ${Math.round(age / 60)} 分钟`
  return null
})
</script>

<template>
  <div v-if="items.length" class="ticker">
    <div class="container ticker__inner">
      <div class="ticker__list">
        <NuxtLink
          v-for="item in items"
          :key="item.code"
          :to="`/market/${item.code}`"
          class="quote"
          :class="toneOf(item.change_pct)"
        >
          <span class="quote__name">{{ item.name }}</span>
          <span class="quote__price num">{{ fmtPoint(item.price) }}</span>
          <span class="quote__pct num">{{ fmtPct(item.change_pct) }}</span>
        </NuxtLink>
      </div>

      <div class="ticker__meta">
        <span class="ticker__status" :class="{ 'is-live': isTrading }">
          <i class="ticker__dot" />
          {{ data?.status_label || '—' }}
        </span>
        <span v-if="timeText" class="ticker__time" :title="data?.degraded_reason ?? ''">
          {{ timeText }}
        </span>
        <span
          v-if="calendarUnknown"
          class="ticker__stale"
          title="交易日历未覆盖当前年份，状态按星期估算"
        >
          日历未覆盖
        </span>
        <span v-if="staleness" class="ticker__stale" :title="data?.degraded_reason ?? ''">
          {{ staleness }}
        </span>
        <span class="ticker__mode" :class="{ 'is-push': streamStatus === 'live' }">
          {{ streamStatus === 'live' ? '推送' : streamStatus === 'polling' ? '轮询' : '连接中' }}
        </span>
        <NuxtLink to="/market" class="ticker__more">大盘 →</NuxtLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ticker {
  background: var(--bg);
  border-bottom: 1px solid var(--line-soft);
}

.ticker__inner {
  display: flex;
  gap: 16px;
  align-items: center;
  height: 40px;
}

.ticker__list {
  display: flex;
  flex: 1;
  gap: 16px;
  align-items: center;
  min-width: 0;
  padding: 0 2px;
  overflow: hidden;
}

.quote {
  display: flex;
  flex: none;
  gap: 6px;
  align-items: baseline;
  font-size: 12.5px;
  white-space: nowrap;
}

.quote__name {
  color: var(--muted);
}

.quote__price {
  font-weight: 600;
  color: var(--ink);
}

.quote__pct {
  font-size: 12px;
  font-weight: 600;
}

.quote.up .quote__price,
.quote.up .quote__pct {
  color: var(--up);
}

.quote.down .quote__price,
.quote.down .quote__pct {
  color: var(--down);
}

.quote.neutral .quote__pct {
  color: var(--muted);
}

.quote:hover .quote__name {
  color: var(--ink);
}

.quote:hover .quote__price {
  text-decoration: underline;
}

.ticker__mode {
  padding: 1px 6px;
  font-size: 10.5px;
  color: var(--muted-2);
  border: 1px solid var(--line);
  border-radius: 999px;
}

.ticker__mode.is-push {
  color: var(--brand);
  background: var(--brand-soft);
  border-color: transparent;
}

.ticker__meta {
  display: flex;
  flex: none;
  gap: 12px;
  align-items: center;
  padding-left: 16px;
  font-size: 11.5px;
  color: var(--muted-2);
  white-space: nowrap;
  border-left: 1px solid var(--line);
}

.ticker__status {
  display: inline-flex;
  gap: 5px;
  align-items: center;
}

.ticker__dot {
  width: 5px;
  height: 5px;
  background: var(--muted-2);
  border-radius: 50%;
}

.ticker__status.is-live {
  color: var(--up);
}

.ticker__status.is-live .ticker__dot {
  background: var(--up);
  animation: pulse 1.8s ease-in-out infinite;
}

@keyframes pulse {
  50% {
    opacity: 0.35;
  }
}

.ticker__time {
  font-family: var(--font-num);
}

.ticker__stale {
  padding: 1px 7px;
  font-size: 11.5px;
  color: #b45309;
  background: #fffbeb;
  border-radius: 999px;
}

.ticker__more {
  font-weight: 600;
  color: var(--brand);
}

.ticker__more:hover {
  text-decoration: underline;
}

/* 宽度不够时从尾部逐个隐藏，宁可少几个指数，也不要出现半截文字 */
@media (max-width: 1180px) {
  .quote:nth-child(n + 6) {
    display: none;
  }
}

@media (max-width: 1000px) {
  .quote:nth-child(n + 5) {
    display: none;
  }
}

@media (max-width: 768px) {
  .quote:nth-child(n + 4) {
    display: none;
  }

  .ticker__meta {
    gap: 8px;
    padding-left: 10px;
  }

  .ticker__time {
    display: none;
  }

  .ticker__mode {
    display: none;
  }
}
</style>
