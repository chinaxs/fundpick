<script setup lang="ts">
import type { HoldingRead, TradeSeed } from '@project/shared'
import { fmtPoint, toneOf } from '@project/shared'
const props = defineProps<{ items: HoldingRead[] }>()
const emit = defineEmits<{ trade: [seed: TradeSeed] }>()
const showClosed = ref(false)
const rows = computed(() =>
  props.items.filter((item) => (showClosed.value ? item.shares === 0 : item.shares > 0)),
)
function open(item: HoldingRead, kind: 'buy' | 'sell') {
  emit('trade', {
    code: item.code,
    name: item.name,
    kind,
    available_shares: item.shares,
  })
}
</script>
<template>
  <section class="p-card">
    <div class="p-head">
      <h2>按基金汇总的持仓</h2>
      <div class="p-tabs">
        <button type="button" :aria-pressed="!showClosed" @click="showClosed = false">持有中</button
        ><button type="button" :aria-pressed="showClosed" @click="showClosed = true">已清仓</button>
      </div>
    </div>

    <div v-if="!rows.length" class="p-empty">
      <h3>{{ showClosed ? '暂无已清仓基金' : '还没有已确认的持仓' }}</h3>
      <p>从「记录买入」开始；已有旧版记录的，请先在下方核对并迁移。</p>
    </div>
    <div
      v-else
      class="p-table-wrap holdings-desktop"
      tabindex="0"
      aria-label="基金持仓，可横向滚动"
    >
      <table class="data-table">
        <thead>
          <tr>
            <th>基金</th>
            <th>持有份额</th>
            <th>剩余成本</th>
            <th>市值 / 净值日期</th>
            <th>{{ showClosed ? '累计收益' : '持有收益' }}</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in rows" :key="item.code">
            <td>
              <NuxtLink :to="`/funds/${item.code}`">{{ item.name }}</NuxtLink
              ><small
                >{{ item.code }}{{ item.estimated_count ? ' · 自动计算' : '' }} · 成本单价
                {{ item.average_cost?.toFixed(6) ?? '—' }}</small
              >
            </td>
            <td class="num">{{ item.shares.toFixed(4) }}</td>
            <td class="num">{{ fmtPoint(item.remaining_cost) }}</td>
            <td class="num">
              {{ fmtPoint(item.market_value)
              }}<small>{{ item.latest_nav_date ?? '暂无净值' }}</small>
            </td>
            <td class="num" :class="toneOf(showClosed ? item.total_profit : item.holding_profit)">
              {{ fmtPoint(showClosed ? item.total_profit : item.holding_profit) }}
            </td>
            <td>
              <div class="p-actions">
                <button type="button" class="p-link" @click="open(item, 'buy')">
                  {{ item.shares ? '加仓' : '再次买入' }}</button
                ><button
                  v-if="item.shares > 0"
                  type="button"
                  class="p-link"
                  @click="open(item, 'sell')"
                >
                  卖出
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="rows.length" class="holding-cards">
      <article v-for="item in rows" :key="item.code" class="holding-card">
        <NuxtLink :to="`/funds/${item.code}`"
          ><strong>{{ item.name }}</strong></NuxtLink
        >
        <small
          >{{ item.code }}{{ item.estimated_count ? ' · 自动计算' : '' }} · 净值日期
          {{ item.latest_nav_date ?? '暂无' }}</small
        >
        <dl>
          <div>
            <dt>份额</dt>
            <dd class="num">{{ item.shares.toFixed(4) }}</dd>
          </div>
          <div>
            <dt>剩余成本</dt>
            <dd class="num">{{ fmtPoint(item.remaining_cost) }}</dd>
          </div>
          <div>
            <dt>市值</dt>
            <dd class="num">{{ fmtPoint(item.market_value) }}</dd>
          </div>
          <div>
            <dt>{{ showClosed ? '累计收益' : '持有收益' }}</dt>
            <dd class="num" :class="toneOf(showClosed ? item.total_profit : item.holding_profit)">
              {{ fmtPoint(showClosed ? item.total_profit : item.holding_profit) }}
            </dd>
          </div>
        </dl>
        <div class="p-actions">
          <button type="button" class="btn btn--ghost" @click="open(item, 'buy')">
            {{ item.shares ? '加仓' : '再次买入' }}
          </button>
          <button v-if="item.shares > 0" type="button" class="btn" @click="open(item, 'sell')">
            卖出
          </button>
        </div>
      </article>
    </div>
  </section>
</template>
