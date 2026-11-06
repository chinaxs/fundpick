<script setup lang="ts">
import type { FundPeriod, FundQuery, FundSortBy, FundType, RiskLevel } from '@project/shared'
import { FUND_PERIOD_MAP, FUND_TYPE_MAP, RISK_LEVEL_MAP } from '@project/shared'

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
// 登录时拉取一次关注集合，供每行星标使用（未登录会直接跳过）
const { load: loadFavorites } = useFavorites()
await loadFavorites()

const state = reactive<FilterState>({
  keyword: (route.query.keyword as string) ?? '',
  type: (route.query.type as FundType) || undefined,
  risk_level: (route.query.risk_level as RiskLevel) || undefined,
  period: ((route.query.period as FundPeriod) || '1y') as FundPeriod,
  sort_by: ((route.query.sort_by as FundSortBy) || 'return') as FundSortBy,
  sort_order: 'desc',
  page: Number(route.query.page) || 1,
  page_size: 20,
})

const params = computed(() => ({ ...state }))
const { data: filters } = await useFundFilters()
const { data, pending } = await useFundList(params)

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

const quickTypes = computed(() => (filters.value?.types ?? []).filter((t) => t.value !== 'other'))

/** 风险等级选项：去掉"风险"后缀，做成短标签（低 / 中低 / 中 / 中高 / 高） */
const riskOptions = computed(() =>
  (filters.value?.risk_levels ?? []).map((opt) => ({
    ...opt,
    label: opt.label.replace(/风险$/, ''),
  })),
)

function clearType() {
  state.type = undefined
  state.page = 1
}

function pickType(type: string) {
  state.type = state.type === type ? undefined : (type as FundType)
  state.page = 1
}

function clearRisk() {
  state.risk_level = undefined
  state.page = 1
}

function pickRisk(value: string) {
  state.risk_level = state.risk_level === value ? undefined : (value as RiskLevel)
  state.page = 1
}

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

function signedPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

/** 幅度类指标（回撤）：取绝对值、不带正负号 */
function plainPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${Math.abs(value).toFixed(2)}%`
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
  if (value === null || value === undefined) return ''
  return value > 0 ? 'up' : value < 0 ? 'down' : ''
}

useSeoMeta({
  title: '基金筛选',
  description: '按收益、回撤、夏普、规模等指标筛选全市场公募基金，支持类型与风险等级过滤。',
})
</script>

<template>
  <div class="page">
    <div class="container">
      <!-- 页头 -->
      <header class="page__head">
        <div>
          <p class="section__eyebrow">Screener</p>
          <h1 class="page__title">基金筛选</h1>
          <p class="page__desc">
            共 <strong class="num">{{ data?.total?.toLocaleString() ?? 0 }}</strong> 只基金 ·
            {{ FUND_PERIOD_MAP[state.period] }}收益 ·
            <span v-if="state.type">{{ FUND_TYPE_MAP[state.type] }} · </span>按{{
              filters?.sort_fields?.find((s) => s.value === state.sort_by)?.label ?? '收益'
            }}排序
          </p>
        </div>
      </header>

      <!-- 筛选面板 -->
      <section class="panel">
        <div class="panel__search">
          <svg class="panel__icon" viewBox="0 0 20 20" aria-hidden="true">
            <circle cx="9" cy="9" r="6.5" fill="none" stroke="currentColor" stroke-width="1.6" />
            <path
              d="M13.5 13.5 18 18"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
            />
          </svg>
          <input
            v-model="state.keyword"
            type="search"
            placeholder="搜索基金代码或名称，回车确认"
            @keyup.enter="state.page = 1"
          />
        </div>

        <div class="panel__row">
          <span class="panel__label">类型</span>
          <div class="panel__chips">
            <button
              type="button"
              class="chip"
              :class="{ 'chip--active': !state.type }"
              @click="clearType"
            >
              全部
            </button>
            <button
              v-for="item in quickTypes"
              :key="item.value"
              type="button"
              class="chip"
              :class="{ 'chip--active': state.type === item.value }"
              @click="pickType(String(item.value))"
            >
              {{ item.label }}
            </button>
          </div>
        </div>

        <div class="panel__row">
          <span class="panel__label">风险</span>
          <div class="panel__chips">
            <button
              type="button"
              class="chip"
              :class="{ 'chip--active': !state.risk_level }"
              @click="clearRisk"
            >
              全部
            </button>
            <button
              v-for="opt in riskOptions"
              :key="opt.value"
              type="button"
              class="chip"
              :class="{ 'chip--active': state.risk_level === opt.value }"
              @click="pickRisk(String(opt.value))"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <div class="panel__row panel__row--foot">
          <div class="panel__selects">
            <FilterDropdown
              v-model="state.period"
              label="区间"
              :options="filters?.periods ?? []"
              @update:model-value="state.page = 1"
            />
            <FilterDropdown
              v-model="state.sort_by"
              label="排序"
              :options="filters?.sort_fields ?? []"
              @update:model-value="state.page = 1"
            />
          </div>

          <button type="button" class="panel__reset" @click="resetFilters">
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M2.5 8a5.5 5.5 0 1 1 1.6 3.9M2.5 12.5V9h3.5"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
            重置筛选
          </button>
        </div>
      </section>

      <!-- 结果 -->
      <div v-if="pending" class="skeleton">
        <div v-for="i in 8" :key="i" class="skeleton__row" />
      </div>

      <div v-else-if="!data?.items?.length" class="empty">
        <div class="empty__title">没有符合条件的基金</div>
        <p class="empty__desc">试试放宽筛选条件，或清空关键词后重新搜索。</p>
        <button type="button" class="btn" @click="resetFilters">重置筛选</button>
      </div>

      <div v-else class="table-wrap">
        <table class="data-table fund-table">
          <thead>
            <tr>
              <th class="col-rank">#</th>
              <th class="col-fav" aria-label="关注"></th>
              <th class="col-name">基金</th>
              <th>类型</th>
              <th class="ta-r">单位净值</th>
              <th class="ta-r">{{ FUND_PERIOD_MAP[state.period] }}收益</th>
              <th class="ta-r">最大回撤</th>
              <th class="ta-r">夏普</th>
              <th class="ta-r">规模</th>
              <th class="col-company">公司 / 经理</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(fund, index) in data.items" :key="fund.id">
              <td class="col-rank num">{{ (state.page - 1) * state.page_size + index + 1 }}</td>
              <td class="col-fav">
                <FavoriteButton :code="fund.code" variant="icon" />
              </td>

              <td class="col-name">
                <NuxtLink :to="`/funds/${fund.code}`" class="fund">
                  <span class="fund__name">{{ fund.name }}</span>
                  <span class="fund__code num">{{ fund.code }}</span>
                </NuxtLink>
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

              <td class="ta-r num">{{ num(fund.latest_nav, 4) }}</td>

              <td class="ta-r num" :class="trendClass(fund.return_rate)">
                <span class="ret" :class="trendClass(fund.return_rate)">
                  {{ signedPct(fund.return_rate) }}
                </span>
              </td>

              <td class="ta-r num muted">{{ plainPct(fund.max_drawdown) }}</td>
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

      <!-- 分页 -->
      <nav v-if="totalPages > 1" class="pager">
        <button type="button" class="pager__btn" :disabled="state.page <= 1" @click="goPage(1)">
          首页
        </button>
        <button
          type="button"
          class="pager__btn"
          :disabled="state.page <= 1"
          @click="goPage(state.page - 1)"
        >
          上一页
        </button>
        <span class="pager__info num">{{ state.page }} / {{ totalPages }}</span>
        <button
          type="button"
          class="pager__btn"
          :disabled="state.page >= totalPages"
          @click="goPage(state.page + 1)"
        >
          下一页
        </button>
        <button
          type="button"
          class="pager__btn"
          :disabled="state.page >= totalPages"
          @click="goPage(totalPages)"
        >
          末页
        </button>
      </nav>

      <p class="disclaimer">
        数据来源于公开渠道，可能存在延迟或误差，仅供参考，不构成投资建议。基金过往业绩不代表未来表现。
      </p>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 44px 0 24px;
}

.page__head {
  margin-bottom: 20px;
}

.page__title {
  margin: 6px 0 0;
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.page__desc {
  margin: 10px 0 0;
  font-size: 13.5px;
  color: var(--muted);
}

.page__desc strong {
  font-size: 15px;
  color: var(--ink);
}

/* ---------------- 筛选面板 ---------------- */
.panel {
  padding: 18px 20px 6px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: 0 1px 2px rgb(15 23 42 / 3%);
}

.panel__search {
  position: relative;
  margin-bottom: 14px;
}

.panel__icon {
  position: absolute;
  top: 50%;
  left: 13px;
  width: 16px;
  height: 16px;
  color: var(--muted-2);
  transform: translateY(-50%);
}

.panel__search input {
  width: 100%;
  height: 42px;
  padding: 0 14px 0 38px;
  font-size: 14px;
  color: var(--ink);
  background: var(--bg-soft);
  border: 1px solid transparent;
  border-radius: 10px;
  outline: none;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.panel__search input:focus {
  background: #fff;
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgb(59 130 246 / 12%);
}

.panel__row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 8px 0;
  border-top: 1px solid var(--line-soft);
}

.panel__label {
  flex: 0 0 32px;
  padding-top: 7px;
  font-size: 12.5px;
  color: var(--muted-2);
}

.panel__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  height: 28px;
  padding: 0 12px;
  font-size: 12.5px;
  color: var(--ink-2);
  cursor: pointer;
  background: var(--bg-soft);
  border: 1px solid transparent;
  border-radius: 999px;
  transition: all 0.15s ease;
}

.chip:hover {
  color: var(--ink);
  background: #e2e8f0;
}

.chip--active {
  color: var(--brand);
  font-weight: 600;
  background: rgb(37 99 235 / 8%);
  border-color: rgb(37 99 235 / 25%);
}

.panel__row--foot {
  justify-content: space-between;
  align-items: center;
  padding: 12px 0 14px;
}

.panel__selects {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.panel__reset {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  height: 32px;
  padding: 0 12px;
  font-size: 12.5px;
  color: var(--muted);
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 8px;
  transition: all 0.15s ease;
}

.panel__reset svg {
  width: 13px;
  height: 13px;
}

.panel__reset:hover {
  color: var(--brand);
  background: rgb(37 99 235 / 6%);
}

/* ---------------- 表格 ---------------- */
.table-wrap {
  overflow-x: auto;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.fund-table {
  min-width: 940px;
}

.col-fav {
  width: 40px;
  padding-right: 0 !important;
  text-align: center;
}

.col-rank {
  width: 52px;
  color: var(--muted-2);
}

.col-name {
  min-width: 230px;
}

.col-company {
  min-width: 160px;
}

.ta-r {
  text-align: right;
}

.fund {
  display: block;
}

.fund__name {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--ink);
}

.fund__name:hover {
  color: var(--brand);
}

.fund__code {
  font-size: 11.5px;
  color: var(--muted-2);
}

.ret {
  display: inline-block;
  min-width: 68px;
  padding: 2px 8px;
  font-weight: 600;
  border-radius: 6px;
}

.ret.up {
  color: var(--up);
  background: var(--up-soft);
}

.ret.down {
  color: var(--down);
  background: var(--down-soft);
}

.muted {
  color: var(--muted);
}

/* ---------------- 类型 + 风险 ---------------- */
.col-type {
  min-width: 110px;
}

.risk {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  margin-top: 5px;
  font-size: 11.5px;
  color: var(--muted);
}

.risk__dot {
  width: 6px;
  height: 6px;
  background: var(--muted-2);
  border-radius: 50%;
}

.risk--low .risk__dot {
  background: #059669;
}

.risk--mid_low .risk__dot {
  background: #0891b2;
}

.risk--mid .risk__dot {
  background: #d97706;
}

.risk--mid_high .risk__dot {
  background: #ea580c;
}

.risk--high .risk__dot {
  background: #dc2626;
}

.risk--low {
  color: #059669;
}

.risk--mid_low {
  color: #0891b2;
}

.risk--mid {
  color: #b45309;
}

.risk--mid_high {
  color: #c2410c;
}

.risk--high {
  color: #dc2626;
}

.risk--unknown {
  color: var(--muted-2);
}

.company {
  font-size: 13px;
  color: var(--ink-2);
}

.manager {
  font-size: 12px;
  color: var(--muted-2);
}

.up {
  color: var(--up);
}

.down {
  color: var(--down);
}

/* ---------------- 骨架屏 ---------------- */
.skeleton {
  padding: 8px 0;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.skeleton__row {
  height: 44px;
  margin: 8px 16px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 37%, #f1f5f9 63%);
  background-size: 400% 100%;
  border-radius: 8px;
  animation: shimmer 1.4s ease infinite;
}

@keyframes shimmer {
  0% {
    background-position: 100% 50%;
  }

  100% {
    background-position: 0 50%;
  }
}

/* ---------------- 空态 ---------------- */
.empty {
  padding: 72px 24px;
  text-align: center;
  background: var(--bg-soft);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

.empty__title {
  font-size: 16px;
  font-weight: 600;
}

.empty__desc {
  margin: 8px 0 20px;
  font-size: 13.5px;
  color: var(--muted);
}

/* ---------------- 分页 ---------------- */
.pager {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
  margin-top: 24px;
}

.pager__btn {
  height: 34px;
  padding: 0 14px;
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 8px;
  transition: all 0.15s ease;
}

.pager__btn:hover:not(:disabled) {
  border-color: #cbd5e1;
  background: var(--bg-soft);
}

.pager__btn:disabled {
  color: #cbd5e1;
  cursor: not-allowed;
}

.pager__info {
  padding: 0 6px;
  font-size: 13px;
  color: var(--muted);
}

.disclaimer {
  margin-top: 32px;
  font-size: 12px;
  line-height: 1.9;
  color: var(--muted-2);
  text-align: center;
}

@media (max-width: 768px) {
  .page__title {
    font-size: 26px;
  }

  .panel {
    padding: 14px 14px 4px;
  }

  .panel__row {
    flex-direction: column;
    gap: 6px;
  }

  .panel__label {
    padding-top: 0;
  }

  .panel__row--foot {
    flex-direction: row;
    flex-wrap: wrap;
    gap: 8px;
  }
}
</style>
