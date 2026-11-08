<script setup lang="ts">
import type { PositionItem, TradeSeed } from '@project/shared'
import { fmtPoint } from '@project/shared'
defineProps<{ items: PositionItem[] }>()
const emit = defineEmits<{ migrate: [seed: TradeSeed] }>()
function review(item: PositionItem) {
  emit('migrate', {
    kind: 'buy',
    code: item.code,
    name: item.name,
    amount: item.amount,
    nav: item.cost_nav,
    confirmed_on: item.bought_at,
    legacy_position_id: item.id,
  })
}
</script>
<template>
  <section v-if="items.length" class="p-card legacy-review">
    <h2>旧版持仓待核对 · {{ items.length }} 笔</h2>
    <p class="p-note">
      这些记录尚未纳入新组合，已按日期从早到晚排列，请依次核对。旧版可能用其他日期净值估算买入，需核对确认日期、金额、净值和手续费，再按平台回执迁移为买入流水；原始记录会保留，避免重复计入。
    </p>
    <div v-for="item in items" :key="item.id" class="legacy-review__row">
      <div>
        <strong>{{ item.name }}</strong
        ><small
          >{{ item.code }} · 原买入日期 {{ item.bought_at }} · 金额 ¥ {{ fmtPoint(item.amount) }} ·
          原成本净值 {{ item.cost_nav.toFixed(4) }}</small
        ><small v-if="item.nav_source === 'latest'">原记录使用了最新净值估算，必须重新核对。</small>
      </div>
      <button type="button" class="btn btn--ghost" @click="review(item)">核对并迁移</button>
    </div>
  </section>
</template>
