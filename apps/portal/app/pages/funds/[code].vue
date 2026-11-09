<script setup lang="ts">
import { ElMessage } from 'element-plus'

import {
  FUND_PERIOD_MAP,
  FUND_SECTOR_MAP,
  FUND_TYPE_MAP,
  NAV_RANGE_MAP,
  NAV_RANGE_ORDER,
  RISK_LEVEL_MAP,
  fmtMagnitude,
  fmtPct,
  toneOf,
  type FundMetric,
  type NavRange,
} from '@project/shared'

const route = useRoute()
const code = String(route.params.code)

const { data: fund } = await useFundDetail(code)
if (!fund.value) {
  throw createError({ statusCode: 404, statusMessage: '基金不存在', fatal: true })
}

const { data: metrics } = await useFundMetrics(code)

// 对比清单：加入后直接跳到对比页，避免"加了但不知道去哪看"
const compareList = useCompareFunds()
function toggleCompare() {
  if (!fund.value) return
  const current = fund.value.code
  if (compareList.codes.value.includes(current)) {
    void navigateTo('/compare')
    return
  }
  if (!compareList.canAdd.value) {
    ElMessage.warning('最多对比 3 只基金，请先在对比页移除一只')
    return
  }
  compareList.add(current)
  void navigateTo('/compare')
}

// 季度重仓股：与 detail/metrics 一样 await 进 SSR（首屏直接可见，SEO 友好）；
// 首次访问未采集的基金会触发实时回填，约多 1 秒
const holdingQuarter = ref<string | null>(null)
const { data: holdings } = await useFundHoldings(code, holdingQuarter)

const topHoldings = computed(() =>
  (holdings.value?.items ?? []).filter((h) => (h.rank ?? 99) <= 10),
)
const hasHoldings = computed(() => (holdings.value?.items ?? []).length > 0)

/** 前十合计占比（模板里保持表达式简单，生产编译器对复杂链式支持不稳） */
const totalRatioText = computed(() =>
  holdings.value?.total_ratio != null ? `${holdings.value.total_ratio.toFixed(2)}%` : '—',
)

/** 占比条宽度：最大 12.5% 封顶（×8 映射到 100%） */
function ratioBarWidth(ratio: number | null): string {
  return `${Math.min(100, (ratio ?? 0) * 8)}%`
}

// 曲线区间：默认近 1 年，切换时自动重新请求（composable 内 watch）
const navRange = ref<NavRange>('1y')
const { data: navs, pending: navsPending } = await useFundNavs(code, navRange)

const navRangeLabel = computed(() => NAV_RANGE_MAP[navRange.value])

/** 历史净值表：与曲线共用同一份数据，最新在前，默认 12 条可展开 */
const navVisible = ref(12)
const navHistory = computed(() => [...(navs.value ?? [])].reverse())
const navShown = computed(() => navHistory.value.slice(0, navVisible.value))
const hasMoreNavs = computed(() => navHistory.value.length > navVisible.value)

function showMoreNavs() {
  navVisible.value += 24
}

function collapseNavs() {
  navVisible.value = 12
}

const metricMap = computed(() => {
  const map = new Map<string, FundMetric>()
  for (const item of metrics.value ?? []) map.set(item.period, item)
  return map
})

const displayPeriods = ['1m', '3m', '6m', '1y', '3y', 'all'] as const
const headline = computed(() => metricMap.value.get('1y'))

const statCards = computed(() => [
  {
    label: '近 1 年收益',
    hint: '越高越好',
    value: fmtPct(headline.value?.return_rate),
    tone: toneOf(headline.value?.return_rate),
  },
  {
    label: '最大回撤',
    hint: '越小越好',
    value: fmtMagnitude(headline.value?.max_drawdown),
    tone: 'neutral' as const,
  },
  {
    label: '夏普比率',
    hint: '风险调整后收益',
    value: headline.value?.sharpe != null ? headline.value.sharpe.toFixed(2) : '—',
    tone: 'neutral' as const,
  },
  {
    label: '年化波动率',
    hint: '越小越稳',
    value: fmtMagnitude(headline.value?.volatility),
    tone: 'neutral' as const,
  },
])

function money(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(2)} 亿元`
}

function fee(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(2)}% / 年`
}

function rowTone(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return ''
  return value > 0 ? 'up' : 'down'
}

function fmtDailyReturn(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

useSeoMeta({
  title: () => `${fund.value?.name ?? ''}（${code}）`,
  description: () =>
    `${fund.value?.name ?? ''} 最新净值 ${fund.value?.latest_nav ?? '—'}，${
      fund.value?.company_name ?? ''
    }旗下${FUND_TYPE_MAP[fund.value?.type ?? 'other']}基金，提供净值走势与区间风险指标。`,
})
</script>

<template>
  <div class="page">
    <div class="container">
      <nav class="crumb">
        <NuxtLink to="/">首页</NuxtLink>
        <span class="crumb__sep">/</span>
        <NuxtLink to="/funds">基金筛选</NuxtLink>
        <span class="crumb__sep">/</span>
        <span class="crumb__current">{{ fund?.name }}</span>
      </nav>

      <!-- 标题区 -->
      <header class="head">
        <div class="head__main">
          <h1 class="head__title">{{ fund?.name }}</h1>
          <div class="head__meta">
            <span class="mono num">{{ fund?.code }}</span>
            <span class="pill">{{ FUND_TYPE_MAP[fund?.type ?? 'other'] }}</span>
            <NuxtLink
              v-if="fund?.sector"
              :to="{ path: '/funds', query: { sector: fund.sector } }"
              class="pill pill--brand pill--link"
              title="按基金名称与跟踪指数归类，查看同板块基金"
            >
              {{ FUND_SECTOR_MAP[fund.sector] }}主题
            </NuxtLink>
            <span
              v-if="fund?.risk_level"
              class="pill"
              :title="`${RISK_LEVEL_MAP[fund.risk_level]}（按基金类型推导，非官方定级）`"
            >
              {{ RISK_LEVEL_MAP[fund.risk_level] }}
            </span>
            <span
              v-if="fund?.share_class"
              class="pill"
              title="同一基金的 A/C 等份额收益接近，但费率与销售服务费不同"
            >
              {{ fund.share_class }} 类份额
            </span>
            <span v-if="fund?.is_index && fund?.tracking_index" class="pill">
              跟踪 {{ fund.tracking_index }}
            </span>
          </div>
        </div>

        <div class="head__side">
          <button type="button" class="pill pill--link compare-btn" @click="toggleCompare">
            加入对比
          </button>
          <FavoriteButton v-if="fund" :code="fund.code" />
          <HoldingBadge :code="code" />
          <FundBuyButton :code="code" :name="fund?.name" :nav-date="fund?.latest_nav_date" />

          <div class="head__nav">
            <span class="head__nav-label">单位净值</span>
            <span class="head__nav-value num">{{ fund?.latest_nav?.toFixed(4) ?? '—' }}</span>
            <span class="head__nav-date">{{ fund?.latest_nav_date ?? '暂无数据' }}</span>
          </div>
        </div>
      </header>

      <!-- 核心指标 -->
      <section class="stats">
        <div v-for="item in statCards" :key="item.label" class="stat">
          <div class="stat__head">
            <span class="stat__label">{{ item.label }}</span>
            <span class="stat__hint">{{ item.hint }}</span>
          </div>
          <div class="stat__value num" :class="`stat__value--${item.tone}`">{{ item.value }}</div>
        </div>
      </section>

      <!-- 净值曲线 -->
      <section class="card block">
        <div class="block__head block__head--wrap">
          <div>
            <h2 class="block__title">净值走势</h2>
            <p class="block__sub">
              {{ navRangeLabel }} · {{ navs?.length ?? 0 }} 个数据点
              <span v-if="navRange === 'all'" class="block__hint">（超长区间已等距抽样）</span>
            </p>
          </div>

          <div class="range">
            <button
              v-for="item in NAV_RANGE_ORDER"
              :key="item"
              type="button"
              class="range__btn"
              :class="{ 'range__btn--active': navRange === item }"
              @click="navRange = item"
            >
              {{ NAV_RANGE_MAP[item] }}
            </button>
          </div>
        </div>

        <div class="chart-wrap" :class="{ 'chart-wrap--pending': navsPending }">
          <FundNavChart :points="navs ?? []" :height="300" />
        </div>
      </section>

      <!-- 历史净值 -->
      <section v-if="navHistory.length" class="card block">
        <div class="block__head">
          <div>
            <h2 class="block__title">历史净值</h2>
            <p class="block__sub">
              {{ navRangeLabel }}共 {{ navHistory.length }} 个交易日 · 按日期倒序
            </p>
          </div>
        </div>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>日期</th>
                <th class="ta-r">单位净值</th>
                <th class="ta-r">日涨跌幅</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in navShown" :key="p.nav_date">
                <td class="num">{{ p.nav_date }}</td>
                <td class="ta-r num">{{ p.unit_nav.toFixed(4) }}</td>
                <td class="ta-r num" :class="rowTone(p.daily_return)">
                  {{ fmtDailyReturn(p.daily_return) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="hasMoreNavs || navVisible > 12" class="nav-more">
          <button v-if="hasMoreNavs" type="button" class="nav-more__btn" @click="showMoreNavs">
            展开更多 · 已显示 {{ navShown.length }} / {{ navHistory.length }}
          </button>
          <button v-else type="button" class="nav-more__btn" @click="collapseNavs">收起</button>
        </div>
      </section>

      <!-- 区间表现 -->
      <section class="card block">
        <div class="block__head">
          <div>
            <h2 class="block__title">区间表现</h2>
            <p class="block__sub">收益为区间累计，回撤与波动为同期风险指标</p>
          </div>
        </div>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>区间</th>
                <th class="ta-r">收益率</th>
                <th class="ta-r">最大回撤</th>
                <th class="ta-r">年化波动率</th>
                <th class="ta-r">夏普比率</th>
                <th class="ta-r">同类排名</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="period in displayPeriods" :key="period">
                <td>
                  {{ FUND_PERIOD_MAP[period] }}
                  <small class="metric-source">
                    <template v-if="metricMap.get(period)?.risk_nav_date">
                      风险数据 {{ metricMap.get(period)?.risk_nav_date }} ·
                      {{ metricMap.get(period)?.risk_source ?? '来源未知' }} · 覆盖
                      {{ metricMap.get(period)?.risk_coverage }}/3
                      <span v-if="metricMap.get(period)?.risk_stale">· 待更新</span>
                    </template>
                    <template v-else>风险指标待采集 · 覆盖 0/3</template>
                  </small>
                </td>
                <td class="ta-r num" :class="rowTone(metricMap.get(period)?.return_rate)">
                  {{ fmtPct(metricMap.get(period)?.return_rate) }}
                </td>
                <td class="ta-r num muted">
                  {{ fmtMagnitude(metricMap.get(period)?.max_drawdown) }}
                </td>
                <td class="ta-r num muted">
                  {{ fmtMagnitude(metricMap.get(period)?.volatility) }}
                </td>
                <td class="ta-r num">{{ metricMap.get(period)?.sharpe?.toFixed(2) ?? '—' }}</td>
                <td class="ta-r num muted">{{ metricMap.get(period)?.rank ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 季度重仓股 -->
      <section v-if="hasHoldings" class="card block">
        <div class="block__head block__head--wrap">
          <div>
            <h2 class="block__title">前十大重仓股</h2>
            <p class="block__sub">
              {{ holdings?.quarter }} 季报披露 · 前十合计占净值 {{ totalRatioText }}
            </p>
          </div>

          <div v-if="(holdings?.quarters ?? []).length > 1" class="range">
            <button
              v-for="q in holdings?.quarters"
              :key="q"
              type="button"
              class="range__btn"
              :class="{ 'range__btn--active': (holdings?.quarter ?? '') === q }"
              @click="holdingQuarter = q"
            >
              {{ q }}
            </button>
          </div>
        </div>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>股票</th>
                <th class="ta-r">占净值比例</th>
                <th class="ta-r">持股数（万股）</th>
                <th class="ta-r">持仓市值（亿元）</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="h in topHoldings" :key="h.stock_code">
                <td class="num muted">{{ h.rank }}</td>
                <td>
                  <span class="holding__name">{{ h.stock_name ?? '—' }}</span>
                  <span class="mono holding__code">{{ h.stock_code }}</span>
                </td>
                <td class="ta-r num">
                  <span class="holding__ratio-bar">
                    <span class="holding__ratio-fill" :style="{ width: ratioBarWidth(h.ratio) }" />
                  </span>
                  {{ h.ratio?.toFixed(2) ?? '—' }}%
                </td>
                <td class="ta-r num muted">
                  {{ h.shares != null ? h.shares.toLocaleString('zh-CN') : '—' }}
                </td>
                <td class="ta-r num muted">
                  {{ h.market_value != null ? h.market_value.toFixed(2) : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 基本信息 -->
      <section class="card block">
        <div class="block__head">
          <div>
            <h2 class="block__title">基本信息</h2>
            <p class="block__sub">基金合同与招募说明书以基金公司公告为准</p>
          </div>
        </div>

        <dl class="info">
          <div class="info__item">
            <dt>基金公司</dt>
            <dd>{{ fund?.company_name ?? '—' }}</dd>
          </div>
          <div class="info__item">
            <dt>基金经理</dt>
            <dd>{{ fund?.manager_name ?? '—' }}</dd>
          </div>
          <div class="info__item">
            <dt>经理任职年限</dt>
            <dd class="num">
              {{ fund?.manager_tenure_years ? `${fund.manager_tenure_years.toFixed(1)} 年` : '—' }}
            </dd>
          </div>
          <div class="info__item">
            <dt>经理管理规模</dt>
            <dd class="num">
              {{ fund?.manager_scale ? `${fund.manager_scale.toFixed(1)} 亿元` : '—' }}
            </dd>
          </div>
          <div class="info__item">
            <dt>基金规模</dt>
            <dd class="num">{{ money(fund?.scale) }}</dd>
          </div>
          <div class="info__item">
            <dt>成立日期</dt>
            <dd class="num">{{ fund?.inception_date ?? '—' }}</dd>
          </div>
          <div class="info__item">
            <dt>管理费率</dt>
            <dd class="num">{{ fee(fund?.fee_rate) }}</dd>
          </div>
          <div class="info__item">
            <dt>托管费率</dt>
            <dd class="num">{{ fee(fund?.custody_fee) }}</dd>
          </div>
        </dl>
      </section>

      <p class="disclaimer">
        数据来源于公开渠道，可能存在延迟或误差，仅供研究参考，不构成投资建议。
        基金过往业绩不代表未来表现，投资前请阅读基金合同与招募说明书，并根据自身风险承受能力独立决策。
      </p>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 28px 0 40px;
}

/* ---------------- 面包屑 ---------------- */
.crumb {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  font-size: 12.5px;
  color: var(--muted-2);
}

.crumb a:hover {
  color: var(--brand);
}

.crumb__sep {
  color: #cbd5e1;
}

.crumb__current {
  color: var(--muted);
}

/* ---------------- 标题区 ---------------- */
.head {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  align-items: flex-end;
  justify-content: space-between;
  padding: 22px 0 24px;
  border-bottom: 1px solid var(--line-soft);
}

.head__title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.head__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 12px;
}

.pill--link:hover {
  border-color: var(--brand);
}

.mono {
  font-family: var(--font-num);
  font-size: 13px;
  color: var(--muted);
}

.head__side {
  display: flex;
  gap: 20px;
  align-items: center;
}

.head__nav {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.head__nav-label {
  font-size: 12px;
  color: var(--muted-2);
}

.head__nav-value {
  font-size: 34px;
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.02em;
}

.head__nav-date {
  font-size: 11.5px;
  color: var(--muted-2);
}

/* ---------------- 指标卡 ---------------- */
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin: 22px 0;
}

.stat {
  padding: 18px 20px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.stat__head {
  display: flex;
  gap: 8px;
  align-items: baseline;
  justify-content: space-between;
}

.stat__label {
  font-size: 12.5px;
  color: var(--muted);
}

.stat__hint {
  font-size: 10.5px;
  color: var(--muted-2);
}

.stat__value {
  margin-top: 10px;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.stat__value--up {
  color: var(--up);
}

.stat__value--down {
  color: var(--down);
}

/* ---------------- 内容块 ---------------- */
.block {
  margin-bottom: 18px;
  padding: 22px 24px;
}

.block__head {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.block__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.block__sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--muted);
}

.block__hint {
  color: var(--muted-2);
}

/* 净值区间切换 */
.range {
  display: inline-flex;
  padding: 3px;
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: 999px;
}

.range__btn {
  padding: 5px 13px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  white-space: nowrap;
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 999px;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.range__btn:hover {
  color: var(--brand);
}

.range__btn--active {
  color: #fff;
  background: var(--brand);
}

.chart-wrap {
  min-height: 300px;
  transition: opacity 0.2s ease;
}

/* 切换区间时轻微淡出，避免旧曲线"跳"一下 */
.chart-wrap--pending {
  opacity: 0.45;
}

.table-wrap {
  overflow-x: auto;
}

.metric-source {
  display: block;
  margin-top: 4px;
  color: var(--muted-2);
  font-size: 11px;
  line-height: 1.4;
}

/* 历史净值展开/收起 */
.nav-more {
  padding-top: 14px;
  text-align: center;
}

.nav-more__btn {
  height: 34px;
  padding: 0 18px;
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: 999px;
  transition: all 0.15s ease;
}

.nav-more__btn:hover {
  color: var(--brand);
  border-color: rgb(37 99 235 / 30%);
}

.ta-r {
  text-align: right;
}

.muted {
  color: var(--muted);
}

.up {
  color: var(--up);
  font-weight: 600;
}

.down {
  color: var(--down);
  font-weight: 600;
}

/* ---------------- 基本信息 ---------------- */
.holding__name {
  font-weight: 500;
}

.holding__code {
  margin-left: 8px;
}

.holding__ratio-bar {
  display: inline-block;
  width: 56px;
  height: 6px;
  margin-right: 8px;
  vertical-align: middle;
  background: var(--bg-soft);
  border-radius: 3px;
}

.holding__ratio-fill {
  display: block;
  height: 100%;
  background: var(--brand);
  border-radius: 3px;
  opacity: 0.55;
}

.info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 2px 28px;
  margin: 0;
}

.info__item {
  display: flex;
  gap: 12px;
  align-items: baseline;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid var(--line-soft);
}

.info dt {
  font-size: 12.5px;
  color: var(--muted);
}

.info dd {
  margin: 0;
  font-size: 13.5px;
  font-weight: 500;
  text-align: right;
}

.disclaimer {
  max-width: 860px;
  margin: 28px auto 0;
  font-size: 12px;
  line-height: 1.9;
  color: var(--muted-2);
  text-align: center;
}

@media (max-width: 900px) {
  .stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .head__title {
    font-size: 23px;
  }

  .head__nav {
    align-items: flex-start;
  }
}

@media (max-width: 520px) {
  .stats {
    grid-template-columns: 1fr;
  }
}
</style>
