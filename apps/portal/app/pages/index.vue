<script setup lang="ts">
import { FUND_TYPE_MAP, type FundType } from '@project/shared'

const { data: stats } = await useOverviewStats()
const { data: dist } = await useReturnDistribution('1y')

const { data: top1y } = await useFundList(
  { period: '1y', sort_by: 'return', page_size: 6 },
  'home-top-1y',
)
const { data: top3y } = await useFundList(
  { period: '3y', sort_by: 'return', page_size: 6 },
  'home-top-3y',
)
const { data: bondTop } = await useFundList(
  { period: '1y', sort_by: 'return', type: 'bond', page_size: 6 },
  'home-bond',
)
const { data: articles } = await useArticleList({ page: 1, page_size: 3 })

const totalFunds = computed(() => stats.value?.total_funds ?? 0)
const totalCompanies = computed(() => stats.value?.total_companies ?? 0)
const latestDate = computed(() => stats.value?.latest_nav_date ?? '—')

/** 正收益基金数量与占比：从分布桶里算，不需要额外请求 */
const positive = computed(() => {
  const buckets = dist.value?.buckets ?? []
  return buckets
    .filter((b) => !b.label.startsWith('-') && !b.label.startsWith('<'))
    .reduce((sum, b) => sum + b.count, 0)
})

const positiveRatio = computed(() => {
  const total = dist.value?.total ?? 0
  return total ? (positive.value / total) * 100 : 0
})

const typeEntries = [
  { type: 'stock' as FundType, desc: '高弹性，追求长期增值' },
  { type: 'hybrid' as FundType, desc: '股债搭配，攻守兼备' },
  { type: 'bond' as FundType, desc: '波动较小，注重稳健' },
  { type: 'index' as FundType, desc: '被动跟踪，费率更低' },
]

const boards = computed(() => [
  { title: '近 1 年收益榜', desc: '过去一年表现最好', data: top1y.value, period: '1y' },
  { title: '近 3 年收益榜', desc: '穿越周期的中长期赢家', data: top3y.value, period: '3y' },
  { title: '债券型精选', desc: '低波动品类领先者', data: bondTop.value, period: '1y' },
])

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

useSeoMeta({
  title: '基金数据分析',
  description: '覆盖全市场公募基金，按收益、回撤、夏普、规模筛选对比，提供净值走势与区间表现。',
  ogTitle: 'Study 基金 · 用数据挑选基金',
})
</script>

<template>
  <div>
    <!-- ============ Hero ============ -->
    <section class="hero">
      <div class="container hero__inner">
        <div class="hero__copy">
          <span class="hero__badge">
            <span class="dot" />
            全市场公募基金 · {{ latestDate }} 更新
          </span>

          <h1 class="hero__title">
            用数据挑基金<br />
            <span class="hero__title-dim">而不是靠感觉</span>
          </h1>

          <p class="hero__desc">
            覆盖
            {{
              totalFunds.toLocaleString()
            }}
            只公募基金，按区间收益、最大回撤、夏普比率、规模多维度筛选。
            每一个排名都可追溯、可复算。
          </p>

          <div class="hero__actions">
            <NuxtLink to="/funds" class="btn">开始筛选</NuxtLink>
            <NuxtLink to="/about" class="btn btn--ghost-light">了解方法</NuxtLink>
          </div>
        </div>

        <!-- 右侧数据卡 -->
        <aside class="hero__panel">
          <div class="panel__head">
            <span class="panel__title">近 1 年收益分布</span>
            <span class="panel__count">{{ (dist?.total ?? 0).toLocaleString() }} 只</span>
          </div>

          <div class="panel__hero">
            <span class="panel__value num">{{ positiveRatio.toFixed(1) }}<i>%</i></span>
            <span class="panel__label">基金取得正收益</span>
          </div>

          <ReturnHistogram :buckets="dist?.buckets ?? []" :height="96" compact />

          <div class="panel__foot">
            <span>正收益 {{ positive.toLocaleString() }} 只</span>
            <span class="panel__sep" />
            <span>负收益 {{ ((dist?.total ?? 0) - positive).toLocaleString() }} 只</span>
          </div>
        </aside>
      </div>

      <!-- 数据条 -->
      <div class="container">
        <dl class="metrics">
          <div class="metrics__item">
            <dt>覆盖基金</dt>
            <dd class="num">{{ totalFunds.toLocaleString() }}</dd>
          </div>
          <div class="metrics__item">
            <dt>基金公司</dt>
            <dd class="num">{{ totalCompanies }}</dd>
          </div>
          <div class="metrics__item">
            <dt>数据口径</dt>
            <dd class="num">T+1 净值</dd>
          </div>
          <div class="metrics__item">
            <dt>最近更新</dt>
            <dd class="num">{{ latestDate }}</dd>
          </div>
        </dl>
      </div>
    </section>

    <!-- ============ 市场结构 ============ -->
    <section class="section section--soft">
      <div class="container">
        <div class="section__head">
          <div>
            <p class="section__eyebrow">Market Structure</p>
            <h2 class="section__title">市场结构</h2>
            <p class="section__desc">
              按基金类型看数量分布与近一年平均收益，快速判断哪类产品正在赚钱。
            </p>
          </div>
          <NuxtLink to="/funds" class="section__more">查看全部基金 →</NuxtLink>
        </div>

        <div class="structure">
          <div class="card structure__chart">
            <TypeBars :items="stats?.type_distribution ?? []" />
          </div>

          <div class="structure__side">
            <NuxtLink
              v-for="item in typeEntries"
              :key="item.type"
              :to="{ path: '/funds', query: { type: item.type } }"
              class="entry"
            >
              <span class="entry__name">{{ FUND_TYPE_MAP[item.type] }}</span>
              <span class="entry__desc">{{ item.desc }}</span>
              <span class="entry__arrow">→</span>
            </NuxtLink>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 收益分布 ============ -->
    <section class="section">
      <div class="container">
        <div class="section__head">
          <div>
            <p class="section__eyebrow">Distribution</p>
            <h2 class="section__title">收益分布</h2>
            <p class="section__desc">
              全市场 {{ (dist?.total ?? 0).toLocaleString() }} 只基金近一年收益分布。
              大部分产品集中在 -10% 到 +10% 之间，极端收益属于少数。
            </p>
          </div>
        </div>

        <div class="card dist-card">
          <ReturnHistogram :buckets="dist?.buckets ?? []" :height="200" />
        </div>
      </div>
    </section>

    <!-- ============ 榜单 ============ -->
    <section class="section section--soft">
      <div class="container">
        <div class="section__head">
          <div>
            <p class="section__eyebrow">Ranking</p>
            <h2 class="section__title">排行榜</h2>
            <p class="section__desc">按区间收益排序，点击进入基金详情查看净值走势与风险指标。</p>
          </div>
          <NuxtLink to="/funds" class="section__more">完整榜单 →</NuxtLink>
        </div>

        <div class="boards">
          <div v-for="board in boards" :key="board.title" class="board">
            <div class="board__head">
              <h3 class="board__title">{{ board.title }}</h3>
              <p class="board__desc">{{ board.desc }}</p>
            </div>

            <ol class="board__list">
              <li v-for="(fund, index) in board.data?.items ?? []" :key="fund.id" class="row">
                <span class="row__rank" :class="{ 'row__rank--top': index < 3 }">{{
                  index + 1
                }}</span>

                <NuxtLink :to="`/funds/${fund.code}`" class="row__fund">
                  <span class="row__name">{{ fund.name }}</span>
                  <span class="row__code num">{{ fund.code }}</span>
                </NuxtLink>

                <span class="row__value num" :class="(fund.return_rate ?? 0) >= 0 ? 'up' : 'down'">
                  {{ fmtPct(fund.return_rate) }}
                </span>
              </li>
            </ol>

            <NuxtLink
              :to="{ path: '/funds', query: { period: board.period, sort_by: 'return' } }"
              class="board__more"
            >
              查看完整榜单
            </NuxtLink>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 研报 ============ -->
    <section v-if="articles?.items?.length" class="section">
      <div class="container">
        <div class="section__head">
          <div>
            <p class="section__eyebrow">Research</p>
            <h2 class="section__title">最新研报</h2>
            <p class="section__desc">市场观察与基金点评</p>
          </div>
          <NuxtLink to="/articles" class="section__more">全部 →</NuxtLink>
        </div>

        <div class="grid">
          <ArticleCard v-for="item in articles.items" :key="item.id" :article="item" />
        </div>
      </div>
    </section>

    <section class="disclaimer-wrap">
      <div class="container">
        <p class="disclaimer">
          本站数据来源于公开渠道，可能存在延迟或误差，仅供研究参考，不构成投资建议。
          基金过往业绩不代表未来表现，投资前请阅读基金合同与招募说明书，并根据自身风险承受能力独立决策。
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* ---------------------------------------------------------------- Hero */
.hero {
  position: relative;
  overflow: hidden;
  background: var(--bg-deep);
}

/* 网格 + 光晕：数据感的主要来源 */
.hero::before {
  position: absolute;
  inset: 0;
  content: '';
  background-image:
    linear-gradient(rgb(255 255 255 / 4%) 1px, transparent 1px),
    linear-gradient(90deg, rgb(255 255 255 / 4%) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(ellipse 90% 70% at 50% 0%, #000 30%, transparent 75%);
}

.hero::after {
  position: absolute;
  top: -180px;
  left: 50%;
  width: 900px;
  height: 480px;
  content: '';
  background: radial-gradient(closest-side, rgb(37 99 235 / 32%), transparent);
  transform: translateX(-50%);
  pointer-events: none;
}

.hero__inner {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 56px;
  align-items: center;
  padding: 84px 24px 64px;
}

.hero__copy {
  max-width: 600px;
}

.hero__badge {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  height: 30px;
  padding: 0 14px;
  font-size: 12px;
  color: #bfdbfe;
  background: rgb(255 255 255 / 6%);
  border: 1px solid rgb(255 255 255 / 12%);
  border-radius: 999px;
}

.dot {
  width: 6px;
  height: 6px;
  background: #4ade80;
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgb(74 222 128 / 20%);
}

.hero__title {
  margin: 22px 0 0;
  font-size: clamp(34px, 4.4vw, 56px);
  font-weight: 800;
  line-height: 1.14;
  color: #fff;
  letter-spacing: -0.03em;
}

.hero__title-dim {
  color: #94a3b8;
}

.hero__desc {
  max-width: 520px;
  margin: 20px 0 0;
  font-size: 16px;
  line-height: 1.85;
  color: #94a3b8;
}

.hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 32px;
}

/* 右侧数据面板 */
.hero__panel {
  padding: 22px 24px;
  background: rgb(255 255 255 / 5%);
  border: 1px solid rgb(255 255 255 / 10%);
  border-radius: 18px;
  backdrop-filter: blur(14px);
}

.panel__head {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}

.panel__title {
  font-size: 13px;
  color: #cbd5e1;
}

.panel__count {
  font-family: var(--font-num);
  font-size: 12px;
  color: #64748b;
}

.panel__hero {
  display: flex;
  gap: 10px;
  align-items: baseline;
  margin: 14px 0 18px;
}

.panel__value {
  font-size: 40px;
  font-weight: 700;
  line-height: 1;
  color: #fff;
  letter-spacing: -0.02em;
}

.panel__value i {
  margin-left: 2px;
  font-size: 18px;
  font-style: normal;
  color: #94a3b8;
}

.panel__label {
  font-size: 13px;
  color: #94a3b8;
}

.panel__foot {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 14px;
  font-size: 12px;
  color: #94a3b8;
}

.panel__sep {
  width: 1px;
  height: 10px;
  background: rgb(255 255 255 / 14%);
}

/* 数据条 */
.metrics {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin: 0;
  border-top: 1px solid rgb(255 255 255 / 8%);
}

.metrics__item {
  padding: 22px 0 26px;
}

.metrics__item + .metrics__item {
  padding-left: 28px;
  border-left: 1px solid rgb(255 255 255 / 8%);
}

.metrics dt {
  font-size: 12px;
  color: #64748b;
}

.metrics dd {
  margin: 6px 0 0;
  font-size: 24px;
  font-weight: 600;
  color: #f1f5f9;
  letter-spacing: -0.01em;
}

/* ---------------------------------------------------------------- 市场结构 */
.structure {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 24px;
}

.structure__chart {
  padding: 26px 28px;
}

.structure__side {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-content: start;
}

.entry {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 20px 18px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;
}

.entry:hover {
  border-color: #cbd5e1;
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.entry__name {
  font-size: 15px;
  font-weight: 600;
}

.entry__desc {
  font-size: 12px;
  line-height: 1.6;
  color: var(--muted);
}

.entry__arrow {
  position: absolute;
  top: 18px;
  right: 16px;
  font-size: 13px;
  color: var(--muted-2);
  transition: transform 0.18s ease;
}

.entry:hover .entry__arrow {
  color: var(--brand);
  transform: translateX(2px);
}

/* ---------------------------------------------------------------- 分布 */
.dist-card {
  padding: 32px 32px 24px;
  box-shadow: var(--shadow-sm);
}

/* ---------------------------------------------------------------- 榜单 */
.boards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.board {
  display: flex;
  flex-direction: column;
  padding: 24px 24px 20px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  transition: box-shadow 0.2s ease;
}

.board:hover {
  box-shadow: var(--shadow-md);
}

.board__head {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line-soft);
}

.board__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.board__desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--muted);
}

.board__list {
  flex: 1;
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
}

.row {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 11px 0;
  border-bottom: 1px solid var(--line-soft);
}

.row:last-child {
  border-bottom: none;
}

.row__rank {
  flex: none;
  width: 22px;
  height: 22px;
  font-family: var(--font-num);
  font-size: 11px;
  line-height: 22px;
  color: var(--muted-2);
  text-align: center;
  background: var(--bg-soft);
  border-radius: 6px;
}

.row__rank--top {
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #334155, #0f172a);
}

.row__fund {
  flex: 1;
  min-width: 0;
}

.row__name {
  display: block;
  overflow: hidden;
  font-size: 13.5px;
  color: var(--ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row__name:hover {
  color: var(--brand);
}

.row__code {
  font-size: 11px;
  color: var(--muted-2);
}

.row__value {
  flex: none;
  font-size: 14px;
  font-weight: 600;
}

.board__more {
  margin-top: 16px;
  font-size: 13px;
  color: var(--brand);
}

.board__more:hover {
  color: var(--brand-dark);
}

/* ---------------------------------------------------------------- 其他 */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
}

.disclaimer-wrap {
  padding: 40px 0 56px;
  background: var(--bg-soft);
  border-top: 1px solid var(--line-soft);
}

.disclaimer {
  max-width: 860px;
  margin: 0 auto;
  font-size: 12.5px;
  line-height: 2;
  color: var(--muted-2);
  text-align: center;
}

.up {
  color: var(--up);
}

.down {
  color: var(--down);
}

@media (max-width: 960px) {
  .hero__inner {
    grid-template-columns: 1fr;
    gap: 36px;
    padding: 56px 24px 48px;
  }

  .structure {
    grid-template-columns: 1fr;
  }

  .boards {
    grid-template-columns: 1fr;
  }

  .metrics {
    grid-template-columns: repeat(2, 1fr);
  }

  .metrics__item:nth-child(3) {
    padding-left: 0;
    border-top: 1px solid rgb(255 255 255 / 8%);
    border-left: none;
  }

  .metrics__item:nth-child(4) {
    border-top: 1px solid rgb(255 255 255 / 8%);
  }
}

@media (max-width: 560px) {
  .structure__side {
    grid-template-columns: 1fr;
  }

  .metrics dd {
    font-size: 20px;
  }
}
</style>
