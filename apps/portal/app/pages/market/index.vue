<script setup lang="ts">
/**
 * 大盘页：8 个核心指数的实时点位 + 日线趋势。
 *
 * 定位是"看环境"而不是"看盘"：列表页只给点位与日线，
 * 想看盘中分时点进单个指数（/market/:code）。
 *
 * 刷新逻辑不在这里：布局里的指数条已经订阅了 SSE，
 * 本页通过 useMarketIndices 共享同一份数据，自动跟着更新。
 */
import { fmtAmountCN, fmtPct, fmtPoint, toneOf } from '@project/shared'

const { data, refresh } = useMarketIndices()
const days = ref(60)
const { data: trends } = await useIndexTrends(days)

const RANGES = [
  { label: '近 1 月', value: 30 },
  { label: '近 3 月', value: 60 },
  { label: '近 6 月', value: 120 },
] as const

const items = computed(() => data.value?.items ?? [])
const isTrading = computed(() => data.value?.market_status === 'trading')

const trendMap = computed(() => {
  const map = new Map<string, { points: number[]; changePct: number | null }>()
  for (const item of trends.value?.items ?? []) {
    map.set(item.code, {
      points: item.points.map((p) => p.close),
      changePct: item.change_pct,
    })
  }
  return map
})

const asOfText = computed(() => {
  if (!data.value?.as_of) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(data.value.as_of))
})

/** 上涨家数：仅用于一句"今天涨跌结构"的概括 */
const upCount = computed(() => items.value.filter((i) => (i.change_pct ?? 0) > 0).length)

useSeoMeta({
  title: '大盘指数 · 上证 / 深证 / 创业板 / 沪深300 实时行情',
  description:
    '上证指数、深证成指、创业板指、科创50、沪深300、中证500、中证1000、北证50 的实时点位与近半年走势，数据来自公开行情源，延迟约数秒到十几秒。',
})
</script>

<template>
  <div class="market">
    <section class="market__head">
      <div class="container">
        <div class="market__head-row">
          <div>
            <p class="market__eyebrow">MARKET · 大盘</p>
            <h1 class="market__title">今日市场</h1>
            <p class="market__desc">
              A 股核心指数的实时点位。行情仅作环境参考，指数本身不可直接投资，
              可通过跟踪该指数的指数基金参与。
            </p>
          </div>

          <div class="status-card">
            <span class="status-card__state" :class="{ 'is-live': isTrading }">
              <i class="status-card__dot" />
              {{ data?.status_label || '行情加载中' }}
            </span>
            <p class="status-card__line">
              <template v-if="data?.trade_date">
                行情日期 <strong>{{ data.trade_date }}</strong>
              </template>
              <template v-else>暂无交易日信息</template>
            </p>
            <p class="status-card__line status-card__line--muted">
              抓取时间 {{ asOfText || '—' }} · {{ data?.source || '公开行情源' }}
            </p>
            <p v-if="items.length" class="status-card__line status-card__line--muted">
              {{ upCount }} / {{ items.length }} 个指数上涨
            </p>
          </div>
        </div>
      </div>
    </section>

    <section class="container market__body">
      <div class="toolbar">
        <p class="toolbar__hint">走势区间</p>
        <div class="segmented">
          <button
            v-for="range in RANGES"
            :key="range.value"
            type="button"
            class="segmented__btn"
            :class="{ 'is-active': days === range.value }"
            @click="days = range.value"
          >
            {{ range.label }}
          </button>
        </div>
      </div>

      <div v-if="items.length" class="grid">
        <NuxtLink
          v-for="item in items"
          :key="item.code"
          :to="`/market/${item.code}`"
          class="idx"
          :class="toneOf(item.change_pct)"
        >
          <header class="idx__head">
            <div>
              <h2 class="idx__name">{{ item.name }}</h2>
              <span class="idx__code">{{ item.code }} · {{ item.group }}</span>
            </div>
            <span class="idx__range" :class="toneOf(trendMap.get(item.code)?.changePct ?? null)">
              {{ fmtPct(trendMap.get(item.code)?.changePct ?? null) }}
              <small>{{ days }} 日</small>
            </span>
          </header>

          <div class="idx__quote">
            <span class="idx__price num">{{ fmtPoint(item.price) }}</span>
            <div class="idx__delta">
              <span class="num">{{ fmtPoint(item.change) }}</span>
              <span class="num idx__pct">{{ fmtPct(item.change_pct) }}</span>
            </div>
          </div>

          <IndexSparkline
            :points="trendMap.get(item.code)?.points ?? []"
            :tone="toneOf(item.change_pct)"
            :height="46"
          />

          <dl class="idx__stats">
            <div>
              <dt>今开</dt>
              <dd class="num">{{ fmtPoint(item.open) }}</dd>
            </div>
            <div>
              <dt>昨收</dt>
              <dd class="num">{{ fmtPoint(item.prev_close) }}</dd>
            </div>
            <div>
              <dt>最高</dt>
              <dd class="num">{{ fmtPoint(item.high) }}</dd>
            </div>
            <div>
              <dt>最低</dt>
              <dd class="num">{{ fmtPoint(item.low) }}</dd>
            </div>
            <div>
              <dt>振幅</dt>
              <dd class="num">
                {{ item.amplitude == null ? '—' : `${item.amplitude.toFixed(2)}%` }}
              </dd>
            </div>
            <div>
              <dt>成交额</dt>
              <dd class="num">{{ fmtAmountCN(item.amount) }}</dd>
            </div>
          </dl>

          <span class="idx__go">查看分时 →</span>
        </NuxtLink>
      </div>

      <div v-else class="empty">
        <p class="empty__title">行情暂时不可用</p>
        <p class="empty__desc">公开行情源偶有波动，稍后刷新即可。基金数据不受影响。</p>
        <button type="button" class="empty__btn" @click="refresh()">重新加载</button>
      </div>

      <p class="footnote">
        数据来自东方财富公开行情（经 AkShare
        获取），盘中延迟约数秒到十几秒，非交易时段展示最近收盘值。 本站不提供 Level-2
        逐笔行情，数据仅作研究参考，不构成投资建议。
      </p>
    </section>
  </div>
</template>

<style scoped>
.market__head {
  background: linear-gradient(180deg, var(--bg-soft) 0%, var(--bg) 100%);
  border-bottom: 1px solid var(--line-soft);
}

.market__head-row {
  display: flex;
  flex-wrap: wrap;
  gap: 32px;
  align-items: flex-end;
  justify-content: space-between;
  padding: 48px 0 40px;
}

.market__eyebrow {
  margin: 0 0 12px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--brand);
}

.market__title {
  margin: 0;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.market__desc {
  max-width: 560px;
  margin: 12px 0 0;
  font-size: 14px;
  line-height: 1.8;
  color: var(--muted);
}

.status-card {
  min-width: 268px;
  padding: 16px 20px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-xs);
}

.status-card__state {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  font-size: 14px;
  font-weight: 700;
  color: var(--ink-2);
}

.status-card__dot {
  width: 6px;
  height: 6px;
  background: var(--muted-2);
  border-radius: 50%;
}

.status-card__state.is-live {
  color: var(--up);
}

.status-card__state.is-live .status-card__dot {
  background: var(--up);
  animation: live 1.8s ease-in-out infinite;
}

@keyframes live {
  50% {
    opacity: 0.3;
  }
}

.status-card__line {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: var(--ink-2);
}

.status-card__line--muted {
  color: var(--muted-2);
}

.market__body {
  padding-top: 28px;
  padding-bottom: 64px;
}

.toolbar {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 20px;
}

.toolbar__hint {
  margin: 0;
  font-size: 12.5px;
  color: var(--muted);
}

.segmented {
  display: inline-flex;
  padding: 3px;
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: 999px;
}

.segmented__btn {
  padding: 5px 14px;
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

.segmented__btn.is-active {
  color: var(--ink);
  background: var(--bg);
  box-shadow: var(--shadow-xs);
}

.grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.idx {
  display: flex;
  flex-direction: column;
  padding: 18px 18px 16px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-xs);
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease,
    border-color 0.2s ease;
}

.idx:hover {
  transform: translateY(-2px);
  border-color: var(--line);
  box-shadow: var(--shadow-md);
}

.idx__head {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  justify-content: space-between;
}

.idx__name {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
}

.idx__code {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: var(--muted-2);
}

.idx__range {
  font-family: var(--font-num);
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  white-space: nowrap;
}

.idx__range small {
  margin-left: 3px;
  font-family: inherit;
  font-size: 10.5px;
  font-weight: 400;
  color: var(--muted-2);
}

.idx__range.up {
  color: var(--up);
}

.idx__range.down {
  color: var(--down);
}

.idx__quote {
  display: flex;
  gap: 10px;
  align-items: baseline;
  margin: 12px 0 4px;
}

.idx__price {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--ink);
}

.idx__delta {
  display: flex;
  gap: 6px;
  align-items: baseline;
  font-size: 12.5px;
  font-weight: 600;
}

.idx__pct {
  font-size: 13px;
}

.idx.up .idx__price,
.idx.up .idx__delta {
  color: var(--up);
}

.idx.down .idx__price,
.idx.down .idx__delta {
  color: var(--down);
}

.idx__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px 6px;
  margin: 12px 0 0;
  padding-top: 12px;
  border-top: 1px solid var(--line-soft);
}

.idx__stats dt {
  font-size: 10.5px;
  color: var(--muted-2);
}

.idx__stats dd {
  margin: 1px 0 0;
  font-size: 12px;
  color: var(--ink-2);
}

.idx__go {
  margin-top: 10px;
  font-size: 11.5px;
  color: var(--muted-2);
  transition: color 0.15s ease;
}

.idx:hover .idx__go {
  color: var(--brand);
}

.empty {
  padding: 64px 24px;
  text-align: center;
  background: var(--bg-soft);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

.empty__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
}

.empty__desc {
  margin: 8px 0 16px;
  font-size: 13px;
  color: var(--muted);
}

.empty__btn {
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  cursor: pointer;
  background: var(--brand);
  border: none;
  border-radius: 999px;
}

.footnote {
  margin: 24px 0 0;
  font-size: 11.5px;
  line-height: 1.9;
  color: var(--muted-2);
}

@media (max-width: 1080px) {
  .grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .market__head-row {
    padding: 32px 0 28px;
  }

  .market__title {
    font-size: 26px;
  }

  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
