<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { FUND_PERIOD_MAP, FUND_SECTOR_MAP, fmtPct, toneOf } from '@project/shared'

const { isLoggedIn, displayName, openAuth, ensureSession } = useAuth()
await ensureSession()

const { codes: favoriteCodes } = useFavorites()
const period = ref('1y')
const { data, pending, refresh } = await useDashboard(period)

const periods = ['1m', '3m', '6m', '1y', '3y'] as const
const summary = computed(() => data.value?.summary)
const positionSummary = computed(() => data.value?.position_summary)

const statCards = computed(() => [
  {
    label: '关注基金',
    value: summary.value?.total_funds?.toLocaleString() ?? '0',
    unit: '只',
    hint: `近 7 天新增 ${summary.value?.added_last_7_days ?? 0} 只`,
    tone: 'neutral' as const,
  },
  {
    label: `${FUND_PERIOD_MAP[period.value as keyof typeof FUND_PERIOD_MAP]}平均收益`,
    value: fmtPct(summary.value?.avg_return),
    unit: '',
    hint: `指标覆盖 ${summary.value?.metric_coverage ?? 0}%`,
    tone: toneOf(summary.value?.avg_return),
  },
  {
    label: '正收益占比',
    value:
      summary.value?.positive_ratio != null ? `${summary.value.positive_ratio.toFixed(1)}%` : '—',
    unit: '',
    hint: '所选区间收益 > 0 的基金',
    tone: 'neutral' as const,
  },
  {
    label: '平均夏普比率',
    value: summary.value?.avg_sharpe != null ? summary.value.avg_sharpe.toFixed(2) : '—',
    unit: '',
    hint: `最佳单只 ${fmtPct(summary.value?.best_return)}`,
    tone: 'neutral' as const,
  },
])

/** 条形图宽度：按当前分组最大值归一化，最小给 4% 保证可见 */
function barWidth(count: number, items: { count: number }[]): string {
  const max = Math.max(1, ...items.map((i) => i.count))
  return `${Math.max(4, (count / max) * 100)}%`
}

const typeItems = computed(() => data.value?.type_distribution ?? [])
const riskItems = computed(() => data.value?.risk_distribution ?? [])
const sectorItems = computed(() => data.value?.sector_distribution ?? [])
const bucketItems = computed(() => data.value?.return_buckets ?? [])
const bucketMax = computed(() => Math.max(1, ...bucketItems.value.map((i) => i.count)))

const riskColors: Record<string, string> = {
  low: '#059669',
  mid_low: '#0891b2',
  mid: '#d97706',
  mid_high: '#ea580c',
  high: '#dc2626',
}

function sectorLabel(key: string): string {
  return FUND_SECTOR_MAP[key as keyof typeof FUND_SECTOR_MAP] ?? key
}

function dateText(value: string | null): string {
  return value ? value.slice(0, 10) : '—'
}

function money(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** 关注数变化（例如在关注页取消）后同步刷新统计 */
watch(
  () => favoriteCodes.value.size,
  () => {
    if (isLoggedIn.value) refresh()
  },
)

async function reload() {
  await refresh()
  ElMessage.success('数据已刷新')
}

useSeoMeta({
  title: '我的工作台',
  description: '统计与展示我关注的基金：收益概览、类型与板块分布、收益榜与模拟持仓概览。',
})
</script>

<template>
  <div class="page">
    <div class="container">
      <header class="head">
        <div>
          <p class="section__eyebrow">Workspace</p>
          <h1 class="head__title">我的工作台</h1>
          <p class="head__sub">
            <template v-if="isLoggedIn">
              {{ displayName }}，这里汇总了你关注的基金表现 ·
              <template v-if="summary?.latest_nav_date">
                净值截至 {{ summary.latest_nav_date }}
              </template>
              <template v-else>暂无净值数据</template>
            </template>
            <template v-else>登录后查看专属的基金数据看板</template>
          </p>
        </div>
        <div v-if="isLoggedIn" class="head__actions">
          <button type="button" class="btn" @click="reload">刷新数据</button>
          <NuxtLink to="/positions" class="btn btn--primary">管理模拟持仓</NuxtLink>
        </div>
      </header>

      <MemberNav />

      <!-- 未登录 -->
      <section v-if="!isLoggedIn" class="empty">
        <div class="empty__icon">▤</div>
        <h2 class="empty__title">登录后开启工作台</h2>
        <p class="empty__desc">关注几只基金，收益概览、类型与板块分布会自动汇总在这里。</p>
        <button type="button" class="btn btn--primary" @click="openAuth('login')">
          登录 / 注册
        </button>
      </section>

      <template v-else>
        <!-- 区间切换 -->
        <div class="toolbar">
          <span class="toolbar__label">统计区间</span>
          <div class="range">
            <button
              v-for="p in periods"
              :key="p"
              type="button"
              class="range__btn"
              :class="{ 'range__btn--active': period === p }"
              @click="period = p"
            >
              {{ FUND_PERIOD_MAP[p] }}
            </button>
          </div>
          <NuxtLink to="/favorites" class="toolbar__link">查看收藏列表 →</NuxtLink>
        </div>

        <div v-if="pending" class="skeleton">
          <div v-for="i in 4" :key="i" class="skeleton__row" />
        </div>

        <template v-else>
          <!-- 尚无关注 -->
          <section v-if="!summary?.total_funds" class="empty">
            <div class="empty__icon">☆</div>
            <h2 class="empty__title">还没有关注任何基金</h2>
            <p class="empty__desc">在基金筛选或详情页点星标，工作台就会开始为你统计。</p>
            <NuxtLink to="/funds" class="btn btn--primary">去挑几只</NuxtLink>
          </section>

          <template v-if="summary?.total_funds">
            <!-- 核心指标 -->
            <section class="stats">
              <div v-for="card in statCards" :key="card.label" class="stat">
                <div class="stat__head">
                  <span class="stat__label">{{ card.label }}</span>
                </div>
                <div class="stat__value num" :class="`stat__value--${card.tone}`">
                  {{ card.value }}<small v-if="card.unit">{{ card.unit }}</small>
                </div>
                <div class="stat__hint">{{ card.hint }}</div>
              </div>
            </section>

            <!-- 分布 -->
            <div class="grid2">
              <section class="card block">
                <div class="block__head">
                  <div>
                    <h2 class="block__title">类型分布</h2>
                    <p class="block__sub">按基金类型统计，括号内为平均收益</p>
                  </div>
                </div>
                <div class="bars">
                  <div v-for="item in typeItems" :key="item.key" class="bar">
                    <span class="bar__label">{{ item.label }}</span>
                    <span class="bar__track">
                      <span class="bar__fill" :style="{ width: barWidth(item.count, typeItems) }" />
                    </span>
                    <span class="bar__value num">
                      {{ item.count }}
                      <small :class="toneOf(item.avg_return)">{{ fmtPct(item.avg_return) }}</small>
                    </span>
                  </div>
                </div>
              </section>

              <section class="card block">
                <div class="block__head">
                  <div>
                    <h2 class="block__title">风险分布</h2>
                    <p class="block__sub">按类型推导的五级风险等级</p>
                  </div>
                </div>
                <div class="bars">
                  <div v-for="item in riskItems" :key="item.key" class="bar">
                    <span class="bar__label">{{ item.label }}</span>
                    <span class="bar__track">
                      <span
                        class="bar__fill"
                        :style="{
                          width: barWidth(item.count, riskItems),
                          background: riskColors[item.key] ?? '#94a3b8',
                        }"
                      />
                    </span>
                    <span class="bar__value num">{{ item.count }}</span>
                  </div>
                  <p v-if="!riskItems.length" class="block__sub">暂无数据</p>
                </div>
              </section>

              <section class="card block">
                <div class="block__head">
                  <div>
                    <h2 class="block__title">板块分布</h2>
                    <p class="block__sub">关注最多的 8 个主题板块</p>
                  </div>
                </div>
                <div v-if="sectorItems.length" class="sectors">
                  <NuxtLink
                    v-for="item in sectorItems"
                    :key="item.key"
                    :to="{ path: '/funds', query: { sector: item.key } }"
                    class="sector-tag"
                  >
                    <span>{{ sectorLabel(item.key) }}</span>
                    <span class="num">{{ item.count }}</span>
                  </NuxtLink>
                </div>
                <p v-else class="block__sub">关注的基金暂无明确主题板块</p>
              </section>

              <section class="card block">
                <div class="block__head">
                  <div>
                    <h2 class="block__title">收益分布</h2>
                    <p class="block__sub">所选区间收益率的分布（基金只数）</p>
                  </div>
                </div>
                <div class="histogram">
                  <div v-for="item in bucketItems" :key="item.key" class="histogram__col">
                    <span class="histogram__count num">{{ item.count }}</span>
                    <span class="histogram__bar-wrap">
                      <span
                        class="histogram__bar"
                        :class="{
                          'histogram__bar--up':
                            item.key.startsWith('>') ||
                            item.key.startsWith('10') ||
                            item.key.startsWith('0'),
                        }"
                        :style="{ height: `${Math.max(3, (item.count / bucketMax) * 100)}%` }"
                      />
                    </span>
                    <span class="histogram__label num">{{ item.key }}</span>
                  </div>
                </div>
              </section>
            </div>

            <!-- 榜单 -->
            <div class="grid2">
              <section class="card block">
                <div class="block__head">
                  <div>
                    <h2 class="block__title">关注基金收益榜</h2>
                    <p class="block__sub">
                      {{ FUND_PERIOD_MAP[period as keyof typeof FUND_PERIOD_MAP] }}收益 Top 5
                    </p>
                  </div>
                </div>
                <div class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th>基金</th>
                        <th class="ta-r">收益率</th>
                        <th class="ta-r">夏普</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="item in data?.top_funds" :key="item.code">
                        <td>
                          <NuxtLink :to="`/funds/${item.code}`" class="fund-link">
                            {{ item.name }}
                          </NuxtLink>
                          <span class="fund-code num">{{ item.code }}</span>
                        </td>
                        <td class="ta-r num" :class="toneOf(item.return_rate)">
                          {{ fmtPct(item.return_rate) }}
                        </td>
                        <td class="ta-r num">
                          {{ item.sharpe != null ? item.sharpe.toFixed(2) : '—' }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </section>

              <section class="card block">
                <div class="block__head">
                  <div>
                    <h2 class="block__title">最近关注</h2>
                    <p class="block__sub">按加入关注的时间倒序</p>
                  </div>
                  <NuxtLink to="/favorites" class="toolbar__link">全部 →</NuxtLink>
                </div>
                <div class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th>基金</th>
                        <th>关注日期</th>
                        <th class="ta-r">单位净值</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="item in data?.recent_funds" :key="item.code">
                        <td>
                          <NuxtLink :to="`/funds/${item.code}`" class="fund-link">
                            {{ item.name }}
                          </NuxtLink>
                          <span class="fund-code num">{{ item.code }}</span>
                        </td>
                        <td class="num muted">{{ dateText(item.favored_at) }}</td>
                        <td class="ta-r num">{{ item.latest_nav?.toFixed(4) ?? '—' }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </template>

          <!-- 模拟持仓概览：明细在独立页面 -->
          <section class="card block teaser">
            <div class="block__head block__head--between">
              <div>
                <h2 class="block__title">模拟持仓 <span class="badge">模拟</span></h2>
                <p class="block__sub">只需记录买入金额与日期，净值由系统自动查询</p>
              </div>
              <NuxtLink to="/positions" class="btn btn--primary">
                {{ positionSummary?.count ? '管理持仓' : '记一笔持仓' }}
              </NuxtLink>
            </div>

            <div class="pos-summary">
              <div class="pos-summary__item">
                <span class="pos-summary__label">持仓笔数</span>
                <span class="pos-summary__value num">{{ positionSummary?.count ?? 0 }}</span>
              </div>
              <div class="pos-summary__item">
                <span class="pos-summary__label">总投入成本</span>
                <span class="pos-summary__value num">
                  ¥ {{ money(positionSummary?.total_amount) }}
                </span>
              </div>
              <div class="pos-summary__item">
                <span class="pos-summary__label">当前市值</span>
                <span class="pos-summary__value num">
                  ¥ {{ money(positionSummary?.total_market_value) }}
                </span>
              </div>
              <div class="pos-summary__item">
                <span class="pos-summary__label">浮动盈亏</span>
                <span class="pos-summary__value num" :class="toneOf(positionSummary?.total_profit)">
                  {{
                    positionSummary?.total_profit != null
                      ? (positionSummary.total_profit > 0 ? '+' : '') +
                        money(positionSummary.total_profit)
                      : '—'
                  }}
                </span>
              </div>
              <div class="pos-summary__item">
                <span class="pos-summary__label">收益率</span>
                <span class="pos-summary__value num" :class="toneOf(positionSummary?.profit_rate)">
                  {{ fmtPct(positionSummary?.profit_rate) }}
                </span>
              </div>
            </div>
          </section>

          <p class="disclaimer">
            收益与风险指标基于所选区间的历史数据，未采集到指标的基金不计入均值。
            模拟持仓仅为个人记录与估算，不代表真实交易；风险等级与主题板块为规则推导，不构成投资建议。
          </p>
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 40px 0 48px;
}

.head {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-end;
  justify-content: space-between;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--line-soft);
}

.head__title {
  margin: 6px 0 0;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.head__sub {
  margin: 9px 0 0;
  font-size: 13.5px;
  color: var(--muted);
}

.head__actions {
  display: flex;
  gap: 8px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin: 0 0 18px;
}

.toolbar__label {
  font-size: 12.5px;
  color: var(--muted-2);
}

.toolbar__link {
  margin-left: auto;
  font-size: 12.5px;
  color: var(--brand);
}

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
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 999px;
  transition: all 0.15s ease;
}

.range__btn:hover {
  color: var(--brand);
}

.range__btn--active {
  color: #fff;
  background: var(--brand);
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 18px;
}

.stat {
  padding: 18px 20px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.stat__label {
  font-size: 12.5px;
  color: var(--muted);
}

.stat__value {
  margin-top: 10px;
  font-size: 27px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.stat__value small {
  margin-left: 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--muted);
}

.stat__value--up {
  color: var(--up);
}

.stat__value--down {
  color: var(--down);
}

.stat__hint {
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--muted-2);
}

.grid2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.block {
  padding: 20px 22px;
  margin-bottom: 16px;
}

.grid2 .block {
  margin-bottom: 0;
}

.block__head {
  margin-bottom: 16px;
}

.block__head--between {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
}

.block__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.block__sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--muted);
}

.badge {
  display: inline-block;
  padding: 2px 7px;
  margin-left: 4px;
  font-size: 10.5px;
  font-weight: 600;
  color: #b45309;
  vertical-align: middle;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 5px;
}

.bars {
  display: grid;
  gap: 11px;
}

.bar {
  display: grid;
  grid-template-columns: 84px 1fr 88px;
  gap: 10px;
  align-items: center;
  font-size: 12.5px;
}

.bar__label {
  color: var(--ink-2);
}

.bar__track {
  height: 8px;
  overflow: hidden;
  background: var(--bg-soft);
  border-radius: 4px;
}

.bar__fill {
  display: block;
  height: 100%;
  background: var(--brand);
  border-radius: 4px;
  opacity: 0.75;
}

.bar__value {
  color: var(--muted);
  text-align: right;
}

.bar__value small {
  display: block;
  font-size: 11px;
}

.sectors {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sector-tag {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  padding: 6px 11px;
  font-size: 12.5px;
  color: var(--ink-2);
  background: var(--bg-soft);
  border: 1px solid var(--line-soft);
  border-radius: 999px;
}

.sector-tag:hover {
  color: var(--brand);
  border-color: var(--brand);
}

.sector-tag .num {
  font-size: 11px;
  color: var(--muted-2);
}

.histogram {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  height: 158px;
}

.histogram__col {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 5px;
  align-items: center;
  height: 100%;
}

.histogram__count {
  font-size: 11px;
  color: var(--muted);
}

.histogram__bar-wrap {
  display: flex;
  flex: 1;
  align-items: flex-end;
  width: 100%;
  max-width: 38px;
}

.histogram__bar {
  width: 100%;
  background: var(--down);
  border-radius: 4px 4px 0 0;
  opacity: 0.75;
}

.histogram__bar--up {
  background: var(--up);
}

.histogram__label {
  font-size: 10.5px;
  color: var(--muted-2);
  white-space: nowrap;
}

.table-wrap {
  overflow-x: auto;
}

.ta-r {
  text-align: right;
}

.fund-link {
  font-size: 13px;
  color: var(--ink);
}

.fund-link:hover {
  color: var(--brand);
}

.fund-code {
  display: block;
  font-size: 11px;
  color: var(--muted-2);
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

.pos-summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  padding: 14px 16px;
  background: var(--bg-soft);
  border: 1px solid var(--line-soft);
  border-radius: 10px;
}

.pos-summary__item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pos-summary__label {
  font-size: 11.5px;
  color: var(--muted-2);
}

.pos-summary__value {
  font-size: 16px;
  font-weight: 700;
}

.skeleton {
  display: grid;
  gap: 12px;
  margin-bottom: 18px;
}

.skeleton__row {
  height: 96px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 37%, #f1f5f9 63%);
  background-size: 400% 100%;
  border-radius: var(--radius);
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

.empty {
  padding: 72px 24px;
  margin-bottom: 18px;
  text-align: center;
  background: var(--bg-soft);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

.empty__icon {
  font-size: 34px;
  color: #cbd5e1;
}

.empty__title {
  margin-top: 8px;
  font-size: 17px;
  font-weight: 600;
}

.empty__desc {
  margin: 8px 0 22px;
  font-size: 13.5px;
  color: var(--muted);
}

.disclaimer {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.9;
  color: var(--muted-2);
  text-align: center;
}

@media (max-width: 900px) {
  .stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .grid2 {
    grid-template-columns: 1fr;
  }

  .pos-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 520px) {
  .stats {
    grid-template-columns: 1fr;
  }

  .head__title {
    font-size: 25px;
  }
}
</style>
