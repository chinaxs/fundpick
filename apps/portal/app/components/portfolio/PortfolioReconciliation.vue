<script setup lang="ts">
import type { Reconciliation } from '~/composables/usePortfolioTools'

/** 收益核对：台账份额/成本 + 公司行为影响。只读汇总。 */
defineProps<{ data: Reconciliation | null; loading: boolean }>()

function money(value: number) {
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function shares(value: number) {
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 4 })
}
</script>

<template>
  <section class="panel">
    <h2 class="panel__title">收益核对</h2>
    <p class="panel__hint">{{ data?.note ?? '按平台回执的买卖流水汇总，公司行为单独列示。' }}</p>

    <p v-if="loading" class="panel__msg">汇总中…</p>
    <template v-else-if="data">
      <div class="totals">
        <div class="total">
          <span>累计投入</span><strong class="num">{{ money(data.invested) }}</strong>
        </div>
        <div class="total">
          <span>累计赎回</span><strong class="num">{{ money(data.redeemed) }}</strong>
        </div>
        <div class="total">
          <span>现金分红</span><strong class="num">{{ money(data.dividends) }}</strong>
        </div>
        <div class="total">
          <span>已实现收益</span><strong class="num">{{ money(data.realized_profit) }}</strong>
        </div>
      </div>

      <p v-if="!data.funds.length" class="panel__msg">还没有可核对的持仓。</p>
      <div v-else class="tools-table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>基金</th>
              <th>回执份额</th>
              <th>剩余成本</th>
              <th>公司行为份额</th>
              <th>核对份额</th>
              <th>现金分红</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="fund in data.funds" :key="fund.code">
              <td>
                {{ fund.name }}<span class="mono">{{ fund.code }}</span>
              </td>
              <td class="num">{{ shares(fund.ledger_shares) }}</td>
              <td class="num">{{ money(fund.ledger_cost) }}</td>
              <td class="num">
                {{ fund.flow_shares_delta ? shares(fund.flow_shares_delta) : '—' }}
              </td>
              <td class="num">{{ shares(fund.expected_shares) }}</td>
              <td class="num">{{ fund.flow_cash ? money(fund.flow_cash) : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="stamp">生成于 {{ new Date(data.generated_at).toLocaleString('zh-CN') }}</p>
    </template>
  </section>
</template>

<style scoped>
.panel {
  padding: 20px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.panel__title {
  margin: 0 0 6px;
  font-size: 17px;
}

.panel__hint {
  margin: 0 0 14px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--muted);
}

.panel__msg {
  margin: 8px 0;
  font-size: 13px;
  color: var(--muted);
}

.totals {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.total {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  font-size: 12px;
  color: var(--muted);
  background: var(--bg-soft);
  border-radius: var(--radius-sm);
}

.total strong {
  font-size: 17px;
  color: var(--ink);
}

.table {
  width: 100%;
  font-size: 12.5px;
  border-collapse: collapse;
}

.table th,
.table td {
  padding: 7px 8px;
  text-align: left;
  border-bottom: 1px solid var(--line-soft);
}

.num {
  font-family: var(--font-num);
  text-align: right;
}

.mono {
  margin-left: 6px;
  font-family: var(--font-num);
  font-size: 11px;
  color: var(--muted-2);
}

.stamp {
  margin: 10px 0 0;
  font-size: 11.5px;
  color: var(--muted-2);
}

@media (max-width: 720px) {
  .totals {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
