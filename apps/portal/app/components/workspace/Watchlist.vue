<script setup lang="ts">
import type { DashboardData, FundPeriod } from '@project/shared'
import { FUND_PERIOD_MAP, fmtPct, toneOf } from '@project/shared'
defineProps<{ data: DashboardData; period: FundPeriod; pending: boolean }>()
const emit = defineEmits<{ 'update:period': [value: FundPeriod] }>()
const periods: FundPeriod[] = ['1m', '3m', '6m', '1y', '3y']
</script>
<template>
  <section class="watchlist card" aria-labelledby="watchlist-title" :aria-busy="pending">
    <div class="block__head block__head--between">
      <h2 id="watchlist-title" class="block__title">
        最近关注 <span class="block__sub">{{ data.summary.total_funds }} 只</span>
      </h2>
      <NuxtLink to="/favorites" class="text-link">查看全部 →</NuxtLink>
    </div>
    <div v-if="data.summary.total_funds" class="watchlist__toolbar">
      <div class="range" aria-label="关注表现区间">
        <button
          v-for="p in periods"
          :key="p"
          type="button"
          class="range__btn"
          :class="{ 'range__btn--active': period === p }"
          :aria-pressed="period === p"
          @click="emit('update:period', p)"
        >
          {{ FUND_PERIOD_MAP[p] }}
        </button>
      </div>
      <span class="block__sub">历史收益，不代表持仓收益</span>
    </div>
    <p v-if="pending" role="status" class="block__sub">正在更新关注表现…</p>
    <div v-if="!data.summary.total_funds" class="watchlist__empty">
      <p>把感兴趣的基金加入关注，方便持续观察。</p>
      <NuxtLink to="/funds" class="text-link">去筛选基金 →</NuxtLink>
    </div>
    <div v-else class="watchlist__rows">
      <div v-for="item in data.recent_funds" :key="item.code" class="watch-row">
        <NuxtLink :to="`/funds/${item.code}`" class="watch-row__fund"
          ><span class="fund-link">{{ item.name }}</span
          ><span class="watch-row__meta"
            ><span class="fund-code num">{{ item.code }}</span
            ><HoldingBadge :code="item.code" /></span
        ></NuxtLink>
        <div class="watch-row__return">
          <span class="block__sub">{{ FUND_PERIOD_MAP[period] }}</span
          ><strong class="num" :class="pending ? '' : toneOf(item.return_rate)">{{
            pending ? '—' : fmtPct(item.return_rate)
          }}</strong>
        </div>
        <FundBuyButton :code="item.code" :name="item.name" compact />
      </div>
    </div>
    <p v-if="data.summary.total_funds && data.summary.metric_coverage < 100" class="block__sub">
      部分基金缺少所选区间指标，以“—”显示。
    </p>
  </section>
</template>
