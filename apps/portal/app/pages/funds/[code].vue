<script setup lang="ts">
import { FUND_PERIOD_MAP, FUND_TYPE_MAP, RISK_LEVEL_MAP, type FundMetric } from '@project/shared'

const route = useRoute()
const code = String(route.params.code)

const { data: fund } = await useFundDetail(code)
if (!fund.value) {
  throw createError({ statusCode: 404, statusMessage: '基金不存在', fatal: true })
}

const { data: metrics } = await useFundMetrics(code)
const { data: navs } = await useFundNavs(code, 500)

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

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

/** 幅度类指标（回撤、波动率）：不带正负号，避免被误读为涨跌 */
function fmtMagnitude(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${Math.abs(value).toFixed(2)}%`
}

function toneOf(value: number | null | undefined): 'up' | 'down' | 'neutral' {
  if (value === null || value === undefined || value === 0) return 'neutral'
  return value > 0 ? 'up' : 'down'
}

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
            <span v-if="fund?.risk_level" class="pill">{{ RISK_LEVEL_MAP[fund.risk_level] }}</span>
            <span v-if="fund?.is_index && fund?.tracking_index" class="pill">
              跟踪 {{ fund.tracking_index }}
            </span>
          </div>
        </div>

        <div class="head__nav">
          <span class="head__nav-label">单位净值</span>
          <span class="head__nav-value num">{{ fund?.latest_nav?.toFixed(4) ?? '—' }}</span>
          <span class="head__nav-date">{{ fund?.latest_nav_date ?? '暂无数据' }}</span>
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
        <div class="block__head">
          <div>
            <h2 class="block__title">净值走势</h2>
            <p class="block__sub">最近 {{ navs?.length ?? 0 }} 个交易日单位净值</p>
          </div>
          <span class="pill">T+1 官方净值</span>
        </div>

        <FundNavChart :points="navs ?? []" :height="300" />
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
                <td>{{ FUND_PERIOD_MAP[period] }}</td>
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

.mono {
  font-family: var(--font-num);
  font-size: 13px;
  color: var(--muted);
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

.table-wrap {
  overflow-x: auto;
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
