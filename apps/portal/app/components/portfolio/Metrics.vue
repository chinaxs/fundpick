<script setup lang="ts">
import type { PortfolioSummary } from '@project/shared'
import { fmtPoint, toneOf } from '@project/shared'
const props = defineProps<{ summary: PortfolioSummary }>()
const hidden = ref(false)
const cards = computed(() => [
  { label: '当前市值', value: props.summary.total_market_value },
  { label: '持有收益', value: props.summary.total_profit, tone: true },
  { label: '累计收益', value: props.summary.total_return, tone: true },
])
function amount(value: number | null) {
  return hidden.value ? '••••••' : fmtPoint(value)
}
</script>
<template>
  <section aria-label="交易记录汇总">
    <div class="p-head metrics-head">
      <span class="p-note">{{ summary.count }} 只持有 · 平台交易记录</span
      ><button type="button" class="p-link" :aria-pressed="hidden" @click="hidden = !hidden">
        {{ hidden ? '显示金额' : '隐藏金额' }}
      </button>
    </div>
    <div class="portfolio-metrics">
      <div v-for="card in cards" :key="card.label" class="p-card">
        <span>{{ card.label }}（元）</span
        ><strong class="num" :class="!hidden && card.tone ? toneOf(card.value) : ''">{{
          amount(card.value)
        }}</strong>
      </div>
    </div>
    <details class="metrics-detail">
      <summary>收益明细与口径</summary>
      <div class="metrics-detail__values">
        <span>剩余成本 ¥ {{ amount(summary.total_amount) }}</span
        ><span>已实现收益 ¥ {{ amount(summary.realized_profit) }}</span
        ><span>累计手续费 ¥ {{ amount(summary.fees) }}</span>
      </div>
      <p class="p-note">
        持有收益 = 市值 − 剩余成本；累计收益 = 持有收益 +
        已实现收益。卖出按移动平均成本结转，清仓后保留历史收益。
      </p>
    </details>
    <p v-if="summary.valued_count < summary.count" class="p-notice" role="status">
      部分基金缺少可用净值，组合市值与收益暂不汇总；已实现收益仍可查看。
    </p>
    <p v-if="summary.estimated_count" class="p-note">
      {{ summary.estimated_count }}
      笔按公开净值和费率自动计算，平台优惠和确认精度可能不同，可核对成交结果。
    </p>
    <p v-if="summary.calculated_count" class="p-notice">
      包含 {{ summary.calculated_count }} 笔旧版折算，尚未核对平台回执；当前汇总不代表平台对账结果。
    </p>
  </section>
</template>
