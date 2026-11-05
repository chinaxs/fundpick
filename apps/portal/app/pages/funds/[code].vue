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

/** period -> 指标，方便模板按行取 */
const metricMap = computed(() => {
  const map = new Map<string, FundMetric>()
  for (const item of metrics.value ?? []) map.set(item.period, item)
  return map
})

const displayPeriods = ['1m', '3m', '6m', '1y', '3y', 'all'] as const

const headline = computed(() => metricMap.value.get('1y'))

const statCards = computed(() => [
  {
    label: '近1年收益',
    value: fmtPct(headline.value?.return_rate),
    tone: toneOf(headline.value?.return_rate),
  },
  {
    label: '最大回撤',
    value: fmtPct(headline.value?.max_drawdown),
    tone: 'neutral' as const,
  },
  {
    label: '夏普比率',
    value: headline.value?.sharpe != null ? headline.value.sharpe.toFixed(2) : '—',
    tone: 'neutral' as const,
  },
  {
    label: '年化波动率',
    value: fmtPct(headline.value?.volatility),
    tone: 'neutral' as const,
  },
])

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
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

useSeoMeta({
  title: () => `${fund.value?.name ?? ''}（${code}）`,
  description: () =>
    `${fund.value?.name ?? ''} 最新净值 ${fund.value?.latest_nav ?? '—'}，${
      fund.value?.company_name ?? ''
    }旗下${FUND_TYPE_MAP[fund.value?.type ?? 'other']}基金。`,
})
</script>

<template>
  <div class="page">
    <div class="container">
      <NuxtLink to="/funds" class="back">← 返回基金筛选</NuxtLink>

      <!-- 标题区 -->
      <header class="head">
        <div>
          <h1 class="head__title">{{ fund?.name }}</h1>
          <div class="head__meta">
            <span class="mono">{{ fund?.code }}</span>
            <span class="tag">{{ FUND_TYPE_MAP[fund?.type ?? 'other'] }}</span>
            <span v-if="fund?.risk_level" class="tag">
              {{ RISK_LEVEL_MAP[fund.risk_level] }}
            </span>
            <span v-if="fund?.is_index && fund?.tracking_index" class="tag">
              跟踪 {{ fund.tracking_index }}
            </span>
          </div>
        </div>

        <div class="head__nav">
          <div class="head__nav-value">{{ fund?.latest_nav?.toFixed(4) ?? '—' }}</div>
          <div class="head__nav-date">单位净值 · {{ fund?.latest_nav_date ?? '暂无数据' }}</div>
        </div>
      </header>

      <!-- 核心指标 -->
      <section class="stats">
        <div v-for="item in statCards" :key="item.label" class="stat">
          <div class="stat__label">{{ item.label }}</div>
          <div class="stat__value" :class="`stat__value--${item.tone}`">{{ item.value }}</div>
        </div>
      </section>

      <!-- 净值曲线 -->
      <section class="card">
        <div class="card__head">
          <h2 class="card__title">净值走势</h2>
          <span class="card__hint">最近 {{ navs?.length ?? 0 }} 个交易日</span>
        </div>
        <FundNavChart :points="navs ?? []" />
      </section>

      <!-- 区间表现 -->
      <section class="card">
        <div class="card__head">
          <h2 class="card__title">区间表现</h2>
          <span class="card__hint">收益为区间累计，回撤/波动为同期风险指标</span>
        </div>

        <div class="table-wrap">
          <table class="metric-table">
            <thead>
              <tr>
                <th>区间</th>
                <th class="text-right">收益率</th>
                <th class="text-right">最大回撤</th>
                <th class="text-right">年化波动率</th>
                <th class="text-right">夏普比率</th>
                <th class="text-right">同类排名</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="period in displayPeriods" :key="period">
                <td>{{ FUND_PERIOD_MAP[period] }}</td>
                <td
                  class="text-right num"
                  :class="
                    toneOf(metricMap.get(period)?.return_rate) === 'up'
                      ? 'num--up'
                      : toneOf(metricMap.get(period)?.return_rate) === 'down'
                        ? 'num--down'
                        : ''
                  "
                >
                  {{ fmtPct(metricMap.get(period)?.return_rate) }}
                </td>
                <td class="text-right num">
                  {{ fmtPct(metricMap.get(period)?.max_drawdown) }}
                </td>
                <td class="text-right num">
                  {{ fmtPct(metricMap.get(period)?.volatility) }}
                </td>
                <td class="text-right num">
                  {{ metricMap.get(period)?.sharpe?.toFixed(2) ?? '—' }}
                </td>
                <td class="text-right num">
                  {{ metricMap.get(period)?.rank ?? '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 基本信息 -->
      <section class="card">
        <div class="card__head">
          <h2 class="card__title">基本信息</h2>
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
            <dt>基金经理任职年限</dt>
            <dd>
              {{ fund?.manager_tenure_years ? `${fund.manager_tenure_years.toFixed(1)} 年` : '—' }}
            </dd>
          </div>
          <div class="info__item">
            <dt>经理管理规模</dt>
            <dd>{{ fund?.manager_scale ? `${fund.manager_scale.toFixed(1)} 亿元` : '—' }}</dd>
          </div>
          <div class="info__item">
            <dt>基金规模</dt>
            <dd>{{ money(fund?.scale) }}</dd>
          </div>
          <div class="info__item">
            <dt>成立日期</dt>
            <dd>{{ fund?.inception_date ?? '—' }}</dd>
          </div>
          <div class="info__item">
            <dt>管理费率</dt>
            <dd>{{ fee(fund?.fee_rate) }}</dd>
          </div>
          <div class="info__item">
            <dt>托管费率</dt>
            <dd>{{ fee(fund?.custody_fee) }}</dd>
          </div>
        </dl>
      </section>

      <p class="disclaimer">
        数据来源于公开渠道，可能存在延迟或误差，仅供参考，不构成投资建议。基金过往业绩不代表未来表现，
        投资前请阅读基金合同与招募说明书。
      </p>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 32px 0 24px;
}

.back {
  font-size: 14px;
  color: var(--color-text-muted);
}

.back:hover {
  color: var(--color-primary);
}

.head {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-items: flex-end;
  justify-content: space-between;
  margin: 20px 0 24px;
}

.head__title {
  margin: 0;
  font-size: 28px;
  letter-spacing: -0.02em;
}

.head__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 10px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 14px;
  color: var(--color-text-muted);
}

.tag {
  padding: 2px 8px;
  font-size: 12px;
  color: var(--color-text-muted);
  background: var(--color-bg-soft);
  border-radius: 4px;
}

.head__nav {
  text-align: right;
}

.head__nav-value {
  font-size: 32px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.head__nav-date {
  margin-top: 4px;
  font-size: 12px;
  color: #a0aec0;
}

.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.stat {
  padding: 18px 20px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.stat__label {
  font-size: 13px;
  color: var(--color-text-muted);
}

.stat__value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.stat__value--up {
  color: #c53030;
}

.stat__value--down {
  color: #2f855a;
}

.card {
  padding: 20px 24px;
  margin-bottom: 20px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.card__head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}

.card__title {
  margin: 0;
  font-size: 17px;
}

.card__hint {
  font-size: 12px;
  color: #a0aec0;
}

.table-wrap {
  overflow-x: auto;
}

.metric-table {
  width: 100%;
  min-width: 620px;
  font-size: 14px;
  border-collapse: collapse;
}

.metric-table th,
.metric-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border);
}

.metric-table th {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted);
  text-align: left;
  background: var(--color-bg-soft);
}

.metric-table tbody tr:last-child td {
  border-bottom: none;
}

.text-right {
  text-align: right;
}

.num {
  font-variant-numeric: tabular-nums;
}

.num--up {
  font-weight: 600;
  color: #c53030;
}

.num--down {
  font-weight: 600;
  color: #2f855a;
}

.info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px 24px;
  margin: 0;
}

.info__item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--color-border);
}

.info dt {
  font-size: 13px;
  color: var(--color-text-muted);
}

.info dd {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  text-align: right;
}

.disclaimer {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.8;
  color: #a0aec0;
  text-align: center;
}
</style>
