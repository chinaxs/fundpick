<script setup lang="ts">
import type { FundPeriod, FundQuery, FundSortBy, FundType, RiskLevel } from '@project/shared'
import { FUND_PERIOD_MAP, FUND_TYPE_MAP } from '@project/shared'

const route = useRoute()
const router = useRouter()

interface FilterState extends FundQuery {
  keyword: string
  period: FundPeriod
  sort_by: FundSortBy
  page: number
  page_size: number
}

/** 筛选状态：初始值从 URL 读，保证链接可分享、刷新不丢条件 */
const state = reactive<FilterState>({
  keyword: (route.query.keyword as string) ?? '',
  type: (route.query.type as FundType) || undefined,
  risk_level: (route.query.risk_level as RiskLevel) || undefined,
  period: ((route.query.period as FundPeriod) || '1y') as FundPeriod,
  sort_by: ((route.query.sort_by as FundSortBy) || 'return') as FundSortBy,
  sort_order: 'desc' as 'asc' | 'desc',
  page: Number(route.query.page) || 1,
  page_size: 20,
})

const params = computed(() => ({ ...state }))
const { data: filters } = await useFundFilters()
const { data, pending } = await useFundList(params)

// 条件变化时同步到 URL（可分享、可收藏）
watch(params, (val) => {
  router.push({
    query: {
      ...val,
      keyword: val.keyword || undefined,
      type: val.type || undefined,
      risk_level: val.risk_level || undefined,
      page: val.page > 1 ? String(val.page) : undefined,
    },
  })
})

const totalPages = computed(() => {
  if (!data.value) return 1
  return Math.max(1, Math.ceil(data.value.total / data.value.page_size))
})

function resetFilters() {
  state.keyword = ''
  state.type = undefined
  state.risk_level = undefined
  state.period = '1y'
  state.sort_by = 'return'
  state.page = 1
}

function goPage(page: number) {
  state.page = Math.min(Math.max(1, page), totalPages.value)
}

/** 收益类数值：正红负绿（中国市场习惯），保留两位 */
function signedPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

function plainPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(2)}%`
}

function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '—'
  return value.toFixed(digits)
}

function money(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  if (value >= 100) return `${(value / 100).toFixed(1)} 百亿`
  return `${value.toFixed(1)} 亿`
}

function trendClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'num'
  return value > 0 ? 'num num--up' : value < 0 ? 'num num--down' : 'num'
}

useSeoMeta({
  title: '基金筛选',
  description: '按收益、回撤、夏普、规模等指标筛选全市场公募基金，支持类型与风险等级过滤。',
})
</script>

<template>
  <div class="page">
    <div class="container">
      <header class="page__head">
        <h1 class="page__title">基金筛选</h1>
        <p class="page__desc">
          共 <strong>{{ data?.total?.toLocaleString() ?? 0 }}</strong> 只基金符合条件 · 区间：{{
            FUND_PERIOD_MAP[state.period]
          }}
        </p>
      </header>

      <!-- 筛选区 -->
      <section class="filters">
        <input
          v-model="state.keyword"
          class="filters__input"
          type="search"
          placeholder="输入基金代码或名称"
          @keyup.enter="state.page = 1"
        />

        <select v-model="state.type" class="filters__select" @change="state.page = 1">
          <option :value="undefined">全部类型</option>
          <option v-for="opt in filters?.types ?? []" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>

        <select v-model="state.risk_level" class="filters__select" @change="state.page = 1">
          <option :value="undefined">全部风险</option>
          <option v-for="opt in filters?.risk_levels ?? []" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>

        <select v-model="state.period" class="filters__select" @change="state.page = 1">
          <option v-for="opt in filters?.periods ?? []" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>

        <select v-model="state.sort_by" class="filters__select" @change="state.page = 1">
          <option v-for="opt in filters?.sort_fields ?? []" :key="opt.value" :value="opt.value">
            按{{ opt.label }}排序
          </option>
        </select>

        <button class="filters__reset" type="button" @click="resetFilters">重置</button>
      </section>

      <!-- 结果 -->
      <div v-if="pending" class="state">加载中…</div>

      <div v-else-if="!data?.items?.length" class="state">
        没有符合条件的基金，试试放宽筛选条件。
      </div>

      <div v-else class="table-wrap">
        <table class="fund-table">
          <thead>
            <tr>
              <th class="col-rank">#</th>
              <th class="col-name">基金</th>
              <th>类型</th>
              <th class="text-right">单位净值</th>
              <th class="text-right">{{ FUND_PERIOD_MAP[state.period] }}收益</th>
              <th class="text-right">最大回撤</th>
              <th class="text-right">夏普</th>
              <th class="text-right">规模</th>
              <th class="col-company">公司 / 经理</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(fund, index) in data.items" :key="fund.id">
              <td class="col-rank">{{ (state.page - 1) * state.page_size + index + 1 }}</td>
              <td class="col-name">
                <NuxtLink :to="`/funds/${fund.code}`" class="fund-name">{{ fund.name }}</NuxtLink>
                <span class="fund-code">{{ fund.code }}</span>
              </td>
              <td>
                <span class="tag">{{ FUND_TYPE_MAP[fund.type] }}</span>
              </td>
              <td class="text-right num">{{ num(fund.latest_nav, 4) }}</td>
              <td class="text-right" :class="trendClass(fund.return_rate)">
                {{ signedPct(fund.return_rate) }}
              </td>
              <td class="text-right num num--muted">{{ plainPct(fund.max_drawdown) }}</td>
              <td class="text-right num">{{ num(fund.sharpe) }}</td>
              <td class="text-right num num--muted">{{ money(fund.scale) }}</td>
              <td class="col-company">
                <div class="company">{{ fund.company_name ?? '—' }}</div>
                <div class="manager">{{ fund.manager_name ?? '—' }}</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <nav v-if="totalPages > 1" class="pager">
        <button type="button" :disabled="state.page <= 1" @click="goPage(state.page - 1)">
          上一页
        </button>
        <span class="pager__info">{{ state.page }} / {{ totalPages }}</span>
        <button type="button" :disabled="state.page >= totalPages" @click="goPage(state.page + 1)">
          下一页
        </button>
      </nav>

      <p class="disclaimer">
        数据来源于公开渠道，仅供参考，不构成投资建议。基金过往业绩不代表未来表现。
      </p>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 40px 0 24px;
}

.page__head {
  margin-bottom: 20px;
}

.page__title {
  margin: 0;
  font-size: 30px;
  letter-spacing: -0.02em;
}

.page__desc {
  margin: 8px 0 0;
  font-size: 14px;
  color: var(--color-text-muted);
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 20px;
}

.filters__input,
.filters__select {
  height: 40px;
  padding: 0 12px;
  font-size: 14px;
  color: var(--color-text);
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.filters__input {
  flex: 1 1 220px;
  min-width: 180px;
}

.filters__select {
  min-width: 120px;
}

.filters__reset {
  height: 40px;
  padding: 0 16px;
  font-size: 14px;
  color: var(--color-text-muted);
  cursor: pointer;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.filters__reset:hover {
  background: var(--color-bg-soft);
}

.state {
  padding: 48px;
  color: var(--color-text-muted);
  text-align: center;
  background: var(--color-bg-soft);
  border-radius: var(--radius);
}

.table-wrap {
  overflow-x: auto;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.fund-table {
  width: 100%;
  min-width: 900px;
  font-size: 14px;
  border-collapse: collapse;
}

.fund-table th,
.fund-table td {
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
}

.fund-table th {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted);
  background: var(--color-bg-soft);
  white-space: nowrap;
}

.fund-table tbody tr:last-child td {
  border-bottom: none;
}

.fund-table tbody tr:hover {
  background: #fafcff;
}

.text-right {
  text-align: right;
}

.col-rank {
  width: 48px;
  color: #a0aec0;
}

.col-name {
  min-width: 220px;
}

.col-company {
  min-width: 150px;
  font-size: 13px;
}

.fund-name {
  display: block;
  font-weight: 500;
  color: var(--color-text);
}

.fund-name:hover {
  color: var(--color-primary);
}

.fund-code {
  font-size: 12px;
  color: #a0aec0;
}

.tag {
  display: inline-block;
  padding: 2px 8px;
  font-size: 12px;
  color: var(--color-text-muted);
  background: var(--color-bg-soft);
  border-radius: 4px;
}

.num {
  font-variant-numeric: tabular-nums;
}

/* 中国市场习惯：涨红跌绿 */
.num--up {
  font-weight: 600;
  color: #c53030;
}

.num--down {
  font-weight: 600;
  color: #2f855a;
}

.num--muted {
  color: var(--color-text-muted);
}

.company {
  color: var(--color-text);
}

.manager {
  color: #a0aec0;
}

.pager {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: center;
  margin-top: 24px;
}

.pager button {
  padding: 8px 18px;
  font-size: 14px;
  color: var(--color-primary);
  cursor: pointer;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 999px;
}

.pager button:disabled {
  color: #cbd5e0;
  cursor: not-allowed;
}

.pager__info {
  font-size: 14px;
  color: var(--color-text-muted);
}

.disclaimer {
  margin-top: 28px;
  font-size: 12px;
  color: #a0aec0;
  text-align: center;
}
</style>
