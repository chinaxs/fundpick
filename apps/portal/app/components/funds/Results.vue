<script setup lang="ts">
import type { FundListItem, FundPeriod, FundSortBy, SortOrder } from '@project/shared'
import {
  FUND_PERIOD_MAP,
  FUND_TYPE_MAP,
  FUND_SECTOR_MAP,
  RISK_LEVEL_MAP,
  fmtPct,
  fmtMagnitude,
  toneOf,
} from '@project/shared'
defineProps<{
  items: FundListItem[]
  page: number
  period: FundPeriod
  sortBy: FundSortBy
  sortOrder: SortOrder
}>()
const emit = defineEmits<{ sort: [field: FundSortBy] }>()
function num(value: number | null | undefined, digits = 2) {
  return value?.toFixed(digits) ?? '—'
}
function money(value: number | null) {
  return value == null ? '—' : `${value.toFixed(1)} 亿`
}
</script>
<template>
  <div class="table-wrap" tabindex="0" aria-label="基金筛选结果，可横向滚动">
    <table class="data-table fund-table">
      <thead>
        <tr>
          <th class="col-rank">#</th>
          <th class="col-fav" aria-label="关注"></th>
          <th class="col-name">基金</th>
          <th>类型</th>
          <th
            class="ta-r"
            :aria-sort="
              sortBy === 'nav' ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'
            "
          >
            <button
              type="button"
              class="sort-button"
              :class="{ 'sort-button--active': sortBy === 'nav' }"
              @click="emit('sort', 'nav')"
            >
              单位净值 {{ sortBy === 'nav' ? (sortOrder === 'asc' ? '↑' : '↓') : '↕' }}
            </button>
          </th>
          <th
            class="ta-r"
            :aria-sort="
              sortBy === 'return' ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'
            "
          >
            <button
              type="button"
              class="sort-button"
              :class="{ 'sort-button--active': sortBy === 'return' }"
              @click="emit('sort', 'return')"
            >
              {{ FUND_PERIOD_MAP[period] }}收益
              {{ sortBy === 'return' ? (sortOrder === 'asc' ? '↑' : '↓') : '↕' }}
            </button>
          </th>
          <th
            class="ta-r"
            :aria-sort="
              sortBy === 'max_drawdown'
                ? sortOrder === 'asc'
                  ? 'ascending'
                  : 'descending'
                : 'none'
            "
          >
            <button
              type="button"
              class="sort-button"
              :class="{ 'sort-button--active': sortBy === 'max_drawdown' }"
              @click="emit('sort', 'max_drawdown')"
            >
              最大回撤 {{ sortBy === 'max_drawdown' ? (sortOrder === 'asc' ? '↑' : '↓') : '↕' }}
            </button>
          </th>
          <th
            class="ta-r"
            :aria-sort="
              sortBy === 'sharpe' ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'
            "
          >
            <button
              type="button"
              class="sort-button"
              :class="{ 'sort-button--active': sortBy === 'sharpe' }"
              @click="emit('sort', 'sharpe')"
            >
              夏普 {{ sortBy === 'sharpe' ? (sortOrder === 'asc' ? '↑' : '↓') : '↕' }}
            </button>
          </th>
          <th
            class="ta-r"
            :aria-sort="
              sortBy === 'scale' ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'
            "
          >
            <button
              type="button"
              class="sort-button"
              :class="{ 'sort-button--active': sortBy === 'scale' }"
              @click="emit('sort', 'scale')"
            >
              规模 {{ sortBy === 'scale' ? (sortOrder === 'asc' ? '↑' : '↓') : '↕' }}
            </button>
          </th>
          <th class="col-company">公司 / 经理</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(fund, index) in items" :key="fund.id">
          <td class="col-rank num">{{ (page - 1) * 20 + index + 1 }}</td>
          <td class="col-fav">
            <FavoriteButton :code="fund.code" variant="icon" />
          </td>

          <td class="col-name">
            <NuxtLink :to="`/funds/${fund.code}`" class="fund">
              <span class="fund__name">{{ fund.name }} <HoldingBadge :code="fund.code" /></span>
              <span class="fund__meta">
                <span class="fund__code num">{{ fund.code }}</span>
                <span v-if="fund.sector" class="fund__sector">
                  {{ FUND_SECTOR_MAP[fund.sector] }}
                </span>
                <span v-else class="fund__sector fund__sector--none">综合</span>
              </span>
            </NuxtLink>
            <div class="fund__action">
              <FundBuyButton
                :code="fund.code"
                :name="fund.name"
                :nav-date="fund.latest_nav_date"
                compact
              />
            </div>
          </td>

          <td class="col-type">
            <span class="pill">{{ FUND_TYPE_MAP[fund.type] }}</span>
            <span
              v-if="fund.risk_level"
              class="risk"
              :class="`risk--${fund.risk_level}`"
              :title="`${RISK_LEVEL_MAP[fund.risk_level]}（按基金类型推导，非官方定级）`"
            >
              <i class="risk__dot" />{{ RISK_LEVEL_MAP[fund.risk_level] }}
            </span>
            <span v-else class="risk risk--unknown">风险待定</span>
          </td>

          <td class="ta-r num">
            {{ num(fund.latest_nav, 4)
            }}<span class="nav-date">{{ fund.latest_nav_date ?? '暂无日期' }}</span>
          </td>

          <td class="ta-r num" :class="toneOf(fund.return_rate)">
            <span class="ret" :class="toneOf(fund.return_rate)">
              {{ fmtPct(fund.return_rate) }}
            </span>
          </td>

          <td class="ta-r num muted">{{ fmtMagnitude(fund.max_drawdown) }}</td>
          <td class="ta-r num">{{ num(fund.sharpe) }}</td>
          <td class="ta-r num muted">{{ money(fund.scale) }}</td>

          <td class="col-company">
            <div class="company">{{ fund.company_name ?? '—' }}</div>
            <div class="manager">{{ fund.manager_name ?? '—' }}</div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<style scoped src="~/assets/css/fund-results.css"></style>
