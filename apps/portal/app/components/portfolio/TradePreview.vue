<script setup lang="ts">
import type { TradePreview } from '@project/shared'
import { fmtPoint, toneOf } from '@project/shared'
defineProps<{ quote: TradePreview }>()
</script>
<template>
  <section class="trade-preview" aria-label="交易确认预览">
    <h3>
      {{ quote.kind === 'buy' ? '买入' : '卖出' }} · {{ quote.name }}<small>{{ quote.code }}</small>
    </h3>
    <dl class="p-detail">
      <div>
        <dt>净值所属日 / 净值</dt>
        <dd>
          {{ quote.confirmed_on
          }}<small
            >{{ quote.nav.toFixed(6) }} ·
            {{ quote.nav_source === 'official' ? '当日官方净值' : '手动填写' }}</small
          >
        </dd>
      </div>
      <div>
        <dt>{{ quote.kind === 'buy' ? '总支出' : '卖出净收入' }}</dt>
        <dd>
          ¥ {{ fmtPoint(quote.cash_amount)
          }}<small
            >{{ quote.kind === 'buy' ? '含' : '已扣' }}手续费 ¥ {{ fmtPoint(quote.fee) }}</small
          >
        </dd>
      </div>
      <div>
        <dt>{{ quote.kind === 'buy' ? '买入份额' : '卖出份额' }}</dt>
        <dd>{{ quote.shares.toFixed(4) }} 份</dd>
      </div>
      <div v-if="quote.kind === 'sell'">
        <dt>本次已实现收益</dt>
        <dd :class="toneOf(quote.realized_profit)">¥ {{ fmtPoint(quote.realized_profit) }}</dd>
      </div>
      <div>
        <dt>该平台入账后持仓</dt>
        <dd>
          {{ quote.remaining_shares.toFixed(4) }} 份<small
            >剩余成本 ¥ {{ fmtPoint(quote.remaining_cost) }}</small
          >
        </dd>
      </div>
    </dl>
  </section>
</template>
