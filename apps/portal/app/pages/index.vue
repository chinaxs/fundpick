<script setup lang="ts">
import { FUND_TYPE_MAP, fmtPct, toneOf, type FundType } from '@project/shared'

const { data: stats } = await useOverviewStats()
const { data: dist } = await useReturnDistribution('1y')

// 三个榜单代表三种选基逻辑：赚得多 / 性价比高 / 体量大
const { data: topReturn } = await useFundList(
  { period: '1y', sort_by: 'return', sort_order: 'desc', page_size: 5 },
  'home-top-return',
)
const { data: topSharpe } = await useFundList(
  { period: '1y', sort_by: 'sharpe', sort_order: 'desc', type: 'hybrid', page_size: 5 },
  'home-top-sharpe',
)
const { data: topScale } = await useFundList(
  { sort_by: 'scale', sort_order: 'desc', page_size: 5 },
  'home-top-scale',
)
const { data: articles } = await useArticleList({ page: 1, page_size: 3 })

const { isLoggedIn, openAuth } = useAuth()

const totalFunds = computed(() => stats.value?.total_funds ?? 0)
const totalCompanies = computed(() => stats.value?.total_companies ?? 0)
const latestDate = computed(() => stats.value?.latest_nav_date ?? '—')

const positiveCount = computed(() => {
  const buckets = dist.value?.buckets ?? []
  const negative = buckets
    .filter((b) => b.label.startsWith('-') || b.label.startsWith('<'))
    .reduce((sum, b) => sum + b.count, 0)
  return Math.max((dist.value?.total ?? 0) - negative, 0)
})

const positiveRatio = computed(() => {
  const total = dist.value?.total ?? 0
  return total > 0 ? (positiveCount.value / total) * 100 : 0
})

const negativeCount = computed(() => Math.max((dist.value?.total ?? 0) - positiveCount.value, 0))

/** 类型间收益差距：衡量"选错类型"的代价 */
const typeSpread = computed(() => {
  const rows = (stats.value?.type_distribution ?? []).filter((t) => t.avg_return !== null)
  if (rows.length < 2) return null
  const sorted = [...rows].sort((a, b) => (b.avg_return ?? 0) - (a.avg_return ?? 0))
  const best = sorted[0]
  const worst = sorted[sorted.length - 1]
  if (!best || !worst) return null
  return {
    best,
    worst,
    gap: (best.avg_return ?? 0) - (worst.avg_return ?? 0),
  }
})

/** 环形进度：正收益占比 */
const GAUGE_R = 58
const gaugeLen = 2 * Math.PI * GAUGE_R
const gaugeOffset = computed(() => gaugeLen * (1 - Math.min(positiveRatio.value, 100) / 100))

const typeCards = computed(() =>
  (stats.value?.type_distribution ?? [])
    .filter((t) => t.count > 0)
    .slice(0, 6)
    .map((t) => ({
      ...t,
      label: t.label || FUND_TYPE_MAP[t.type as FundType] || t.type,
      tone: t.avg_return === null ? 'neutral' : t.avg_return >= 0 ? 'up' : 'down',
    })),
)

const boards = computed(() => [
  {
    key: 'return',
    title: '近 1 年收益榜',
    hint: '赚得最多的产品，往往也伴随更大的波动',
    items: topReturn.value?.items ?? [],
    metric: (item: { return_rate: number | null }) => fmtPct(item.return_rate),
    tone: (item: { return_rate: number | null }) => toneOf(item.return_rate),
  },
  {
    key: 'sharpe',
    title: '夏普比率榜',
    hint: '每承担一份波动换来的收益，混合型范围内比较',
    items: topSharpe.value?.items ?? [],
    metric: (item: { sharpe: number | null }) =>
      item.sharpe == null ? '—' : item.sharpe.toFixed(2),
    tone: () => 'neutral' as const,
  },
  {
    key: 'scale',
    title: '规模榜',
    hint: '资金用脚投票的结果，规模过小需留意清盘风险',
    items: topScale.value?.items ?? [],
    metric: (item: { scale: number | null }) =>
      item.scale == null ? '—' : `${item.scale.toFixed(0)} 亿`,
    tone: () => 'neutral' as const,
  },
])

useSeoMeta({
  title: 'Study 基金 · 用数据挑基金',
  description:
    '覆盖全市场公募基金的筛选与排行工具。按区间收益、最大回撤、夏普比率、规模多维度筛选，每个排名可追溯、口径可复算。',
})
</script>

<template>
  <div class="home">
    <!-- ============ 首屏 ============ -->
    <section class="hero">
      <div class="hero__grid" aria-hidden="true" />
      <div class="container hero__inner">
        <div class="hero__copy">
          <p class="hero__eyebrow">
            <span class="dot" />
            全市场公募基金 · {{ latestDate }} 更新
          </p>

          <h1 class="hero__title">
            用数据挑基金<br />
            <span class="hero__title-accent">而不是靠感觉</span>
          </h1>

          <p class="hero__desc">
            覆盖 {{ totalFunds.toLocaleString() }} 只公募基金，按区间收益、最大回撤、夏普比率、
            规模多维度筛选。每个排名都可追溯、口径可复算。
          </p>

          <div class="hero__actions">
            <NuxtLink to="/funds" class="btn btn--primary">
              开始筛选
              <span class="btn__arrow">→</span>
            </NuxtLink>
            <NuxtLink
              :to="{ path: '/funds', query: { period: '1y', sort_by: 'return' } }"
              class="btn btn--ghost-light"
            >
              看收益排行
            </NuxtLink>
          </div>

          <dl class="hero__facts">
            <div>
              <dt>覆盖基金</dt>
              <dd>{{ totalFunds.toLocaleString() }}</dd>
            </div>
            <div>
              <dt>基金公司</dt>
              <dd>{{ totalCompanies }}</dd>
            </div>
            <div>
              <dt>数据口径</dt>
              <dd>T+1 净值</dd>
            </div>
          </dl>
        </div>

        <!-- 市场温度 -->
        <div class="temp">
          <div class="temp__head">
            <span class="temp__label">市场温度 · 近 1 年</span>
            <span class="temp__badge">{{ positiveCount.toLocaleString() }} 只上涨</span>
          </div>

          <div class="gauge">
            <svg class="gauge__svg" viewBox="0 0 140 140">
              <defs>
                <linearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stop-color="#60a5fa" />
                  <stop offset="100%" stop-color="#2563eb" />
                </linearGradient>
              </defs>
              <circle cx="70" cy="70" :r="GAUGE_R" class="gauge__track" />
              <circle
                cx="70"
                cy="70"
                :r="GAUGE_R"
                class="gauge__fill"
                :stroke-dasharray="gaugeLen"
                :style="{ '--len': gaugeLen, '--target': gaugeOffset }"
              />
            </svg>
            <div class="gauge__center">
              <strong>{{ positiveRatio.toFixed(1) }}<small>%</small></strong>
              <span>取得正收益</span>
            </div>
          </div>

          <div class="temp__split">
            <div class="temp__side">
              <span class="temp__num">{{ positiveCount.toLocaleString() }}</span>
              <span class="temp__tag">上涨</span>
            </div>
            <div class="temp__bar">
              <span class="temp__bar-up" :style="{ width: `${Math.min(positiveRatio, 100)}%` }" />
            </div>
            <div class="temp__side temp__side--down">
              <span class="temp__num">{{ negativeCount.toLocaleString() }}</span>
              <span class="temp__tag">下跌</span>
            </div>
          </div>

          <p class="temp__foot">
            统计口径：近 1 年有可比净值的 {{ (dist?.total ?? 0).toLocaleString() }} 只基金
          </p>
        </div>
      </div>
    </section>

    <!-- ============ 三条洞察 ============ -->
    <section class="section insights">
      <div class="container">
        <div class="insights__grid">
          <article class="insight">
            <p class="insight__label">赚钱效应</p>
            <p class="insight__value">
              {{ positiveRatio.toFixed(1) }}<span class="insight__unit">%</span>
            </p>
            <p class="insight__desc">
              近一年取得正收益的基金占比。
              <strong>低于 50% 意味着多数产品在亏钱</strong>，此时选基比择时更重要。
            </p>
          </article>

          <article v-if="typeSpread" class="insight">
            <p class="insight__label">类型分化</p>
            <p class="insight__value">
              {{ typeSpread.gap.toFixed(1) }}<span class="insight__unit">pp</span>
            </p>
            <p class="insight__desc">
              {{ typeSpread.best.label }} 平均
              <strong class="up">{{ fmtPct(typeSpread.best.avg_return) }}</strong
              >， {{ typeSpread.worst.label }} 平均
              <strong class="down">{{ fmtPct(typeSpread.worst.avg_return) }}</strong
              >。 选错类型的代价可能超过选错产品。
            </p>
          </article>

          <article class="insight">
            <p class="insight__label">怎么看排名</p>
            <p class="insight__value insight__value--text">收益 ≠ 性价比</p>
            <p class="insight__desc">
              同样 +20% 的收益，最大回撤 10% 与 40% 的持有体验完全不同。
              建议同时看<strong>夏普比率</strong>与<strong>最大回撤</strong>。
            </p>
          </article>
        </div>
      </div>
    </section>

    <!-- ============ 按类型找 ============ -->
    <section class="section section--soft">
      <div class="container">
        <div class="section__head">
          <div>
            <h2 class="section__title">按类型找基金</h2>
            <p class="section__sub">先定类型再选产品，比直接看排行榜更有效</p>
          </div>
          <NuxtLink to="/funds" class="link-more">全部基金 →</NuxtLink>
        </div>

        <div class="types">
          <NuxtLink
            v-for="item in typeCards"
            :key="item.type"
            :to="{ path: '/funds', query: { type: item.type } }"
            class="type-card"
          >
            <span class="type-card__name">{{ item.label }}</span>
            <span class="type-card__count">{{ item.count.toLocaleString() }} 只</span>
            <span class="type-card__ret" :class="item.tone">
              {{ item.avg_return === null ? '—' : fmtPct(item.avg_return) }}
              <small>近 1 年</small>
            </span>
          </NuxtLink>
        </div>
      </div>
    </section>

    <!-- ============ 榜单 ============ -->
    <section class="section">
      <div class="container">
        <div class="section__head">
          <div>
            <h2 class="section__title">今日榜单</h2>
            <p class="section__sub">三种选基逻辑，对应三种不同的持有目标</p>
          </div>
          <NuxtLink to="/funds" class="link-more">自定义筛选 →</NuxtLink>
        </div>

        <div class="boards">
          <div v-for="board in boards" :key="board.key" class="board">
            <div class="board__head">
              <h3 class="board__title">{{ board.title }}</h3>
              <p class="board__hint">{{ board.hint }}</p>
            </div>

            <ol class="rank">
              <li v-for="(item, index) in board.items" :key="item.code" class="rank__item">
                <span class="rank__no" :class="{ 'rank__no--top': index < 3 }">{{
                  index + 1
                }}</span>
                <NuxtLink :to="`/funds/${item.code}`" class="rank__main">
                  <span class="rank__name">{{ item.name }}</span>
                  <span class="rank__meta">{{ item.code }} · {{ item.company_name || '—' }}</span>
                </NuxtLink>
                <span class="rank__value num" :class="board.tone(item)">
                  {{ board.metric(item) }}
                </span>
              </li>
              <li v-if="board.items.length === 0" class="rank__empty">暂无数据</li>
            </ol>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 研报 ============ -->
    <section v-if="articles?.items?.length" class="section section--soft">
      <div class="container">
        <div class="section__head">
          <div>
            <h2 class="section__title">市场观察</h2>
            <p class="section__sub">数据背后的结构性变化</p>
          </div>
          <NuxtLink to="/articles" class="link-more">全部研报 →</NuxtLink>
        </div>

        <div class="posts">
          <ArticleCard v-for="item in articles.items" :key="item.id" :article="item" />
        </div>
      </div>
    </section>

    <!-- ============ 注册引导 ============ -->
    <section v-if="!isLoggedIn" class="cta-band">
      <div class="container cta-band__inner">
        <div>
          <h2 class="cta-band__title">注册一个账号</h2>
          <p class="cta-band__desc">
            保存常用筛选口径与关注列表，下次打开直接看结论。当前一期先开放账号体系，个人功能陆续上线。
          </p>
        </div>
        <div class="cta-band__actions">
          <button type="button" class="btn btn--primary" @click="openAuth('register')">
            免费注册
          </button>
          <button type="button" class="btn btn--ghost-light" @click="openAuth('login')">
            已有账号，登录
          </button>
        </div>
      </div>
    </section>

    <div class="disclaimer-wrap">
      <div class="container">
        <p class="disclaimer">
          本站数据来自公开渠道，仅作研究参考，不构成投资建议。基金过往业绩不代表未来表现。
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ================================================================ 首屏 */
.hero {
  position: relative;
  overflow: hidden;
  color: #e2e8f0;
  background:
    radial-gradient(900px 420px at 78% -8%, rgb(37 99 235 / 32%), transparent 62%),
    linear-gradient(180deg, #0b1220 0%, #0f172a 100%);
}

.hero__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgb(255 255 255 / 4%) 1px, transparent 1px),
    linear-gradient(90deg, rgb(255 255 255 / 4%) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(760px 420px at 30% 22%, #000 12%, transparent 76%);
}

.hero__inner {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  gap: 56px;
  align-items: center;
  padding-top: 76px;
  padding-bottom: 84px;
}

.hero__eyebrow {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  margin: 0 0 20px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: #94a3b8;
  text-transform: uppercase;
}

.dot {
  width: 6px;
  height: 6px;
  background: #22c55e;
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgb(34 197 94 / 18%);
}

.hero__title {
  margin: 0;
  font-size: 54px;
  font-weight: 800;
  line-height: 1.18;
  letter-spacing: -0.02em;
  color: #f8fafc;
}

.hero__title-accent {
  color: #60a5fa;
}

.hero__desc {
  max-width: 480px;
  margin: 20px 0 0;
  font-size: 15px;
  line-height: 1.9;
  color: #94a3b8;
}

.hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 32px;
}

.btn {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  padding: 12px 24px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  border-radius: 999px;
  transition:
    transform 0.15s ease,
    background 0.15s ease,
    border-color 0.15s ease;
}

.btn:hover {
  transform: translateY(-1px);
}

.btn--primary {
  color: #fff;
  background: var(--brand);
  box-shadow: 0 10px 24px -8px rgb(37 99 235 / 60%);
}

.btn--primary:hover {
  background: var(--brand-dark);
}

.btn__arrow {
  transition: transform 0.15s ease;
}

.btn--primary:hover .btn__arrow {
  transform: translateX(3px);
}

.btn--ghost-light {
  color: #e2e8f0;
  background: rgb(255 255 255 / 6%);
  border-color: rgb(255 255 255 / 14%);
}

.btn--ghost-light:hover {
  background: rgb(255 255 255 / 12%);
  border-color: rgb(255 255 255 / 26%);
}

.hero__facts {
  display: flex;
  flex-wrap: wrap;
  gap: 40px;
  margin: 44px 0 0;
  padding-top: 24px;
  border-top: 1px solid rgb(255 255 255 / 8%);
}

.hero__facts dt {
  font-size: 12px;
  color: #64748b;
}

.hero__facts dd {
  margin: 4px 0 0;
  font-family: var(--font-num);
  font-size: 20px;
  font-weight: 700;
  color: #f1f5f9;
}

/* ---- 市场温度卡 ---- */
.temp {
  padding: 26px 26px 22px;
  background: rgb(255 255 255 / 5%);
  border: 1px solid rgb(255 255 255 / 10%);
  border-radius: 22px;
  box-shadow: 0 30px 60px -30px rgb(2 6 23 / 80%);
  backdrop-filter: blur(14px);
}

.temp__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.temp__label {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  letter-spacing: 0.04em;
}

.temp__badge {
  padding: 3px 9px;
  font-size: 11px;
  color: #fca5a5;
  background: rgb(220 38 38 / 14%);
  border-radius: 999px;
}

.gauge {
  position: relative;
  display: grid;
  place-items: center;
  margin: 6px 0 2px;
}

.gauge__svg {
  width: 180px;
  height: 180px;
  transform: rotate(-90deg);
}

.gauge__track {
  fill: none;
  stroke: rgb(255 255 255 / 9%);
  stroke-width: 12;
}

.gauge__fill {
  fill: none;
  stroke: url(#gaugeGrad);
  stroke-width: 12;
  stroke-linecap: round;
  stroke-dashoffset: var(--target);
  animation: gauge-in 1.1s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes gauge-in {
  from {
    stroke-dashoffset: var(--len);
  }
}

.gauge__center {
  position: absolute;
  text-align: center;
}

.gauge__center strong {
  display: block;
  font-family: var(--font-num);
  font-size: 40px;
  font-weight: 700;
  line-height: 1;
  color: #f8fafc;
}

.gauge__center small {
  font-size: 18px;
  color: #94a3b8;
}

.gauge__center span {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: #94a3b8;
}

.temp__split {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 4px;
  padding: 14px 0 0;
  border-top: 1px solid rgb(255 255 255 / 8%);
}

.temp__side {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 56px;
}

.temp__side--down {
  align-items: flex-end;
}

.temp__num {
  font-family: var(--font-num);
  font-size: 14px;
  font-weight: 700;
  color: #e2e8f0;
}

.temp__tag {
  font-size: 11px;
  color: #64748b;
}

.temp__bar {
  flex: 1;
  height: 6px;
  overflow: hidden;
  background: #10b981;
  border-radius: 999px;
}

.temp__bar-up {
  display: block;
  height: 100%;
  background: #ef4444;
  border-radius: 999px;
  transition: width 0.9s cubic-bezier(0.22, 1, 0.36, 1);
}

.temp__foot {
  margin: 14px 0 0;
  font-size: 11px;
  color: #475569;
}

/* ================================================================ 洞察 */
.insights {
  padding-top: 56px;
  padding-bottom: 56px;
}

.insights__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

.insight {
  padding: 24px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-xs);
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.insight:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.insight__label {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  letter-spacing: 0.04em;
}

.insight__value {
  margin: 10px 0 0;
  font-family: var(--font-num);
  font-size: 34px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--ink);
}

.insight__value--text {
  font-family: inherit;
  font-size: 22px;
}

.insight__unit {
  margin-left: 2px;
  font-size: 16px;
  color: var(--muted);
}

.insight__desc {
  margin: 12px 0 0;
  font-size: 13px;
  line-height: 1.85;
  color: var(--muted);
}

.insight__desc strong {
  color: var(--ink-2);
}

/* ================================================================ 类型 */
.types {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.type-card {
  display: grid;
  gap: 6px;
  padding: 20px 22px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  transition:
    border-color 0.15s ease,
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.type-card:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.type-card__name {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
}

.type-card__count {
  font-size: 12px;
  color: var(--muted);
}

.type-card__ret {
  margin-top: 6px;
  font-family: var(--font-num);
  font-size: 19px;
  font-weight: 700;
}

.type-card__ret small {
  margin-left: 6px;
  font-family: inherit;
  font-size: 11px;
  font-weight: 400;
  color: var(--muted-2);
}

/* ================================================================ 榜单 */
.boards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

.board {
  padding: 20px 4px 8px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.board__head {
  padding: 0 18px 14px;
  border-bottom: 1px solid var(--line-soft);
}

.board__title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
}

.board__hint {
  margin: 5px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--muted);
}

.rank {
  margin: 0;
  padding: 6px 0 0;
  list-style: none;
}

.rank__item {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 11px 18px;
  transition: background 0.12s ease;
}

.rank__item:hover {
  background: var(--bg-soft);
}

.rank__no {
  flex: none;
  width: 22px;
  height: 22px;
  font-family: var(--font-num);
  font-size: 12px;
  font-weight: 700;
  line-height: 22px;
  color: var(--muted);
  text-align: center;
  background: var(--bg-soft);
  border-radius: 7px;
}

.rank__no--top {
  color: #fff;
  background: var(--brand);
}

.rank__main {
  flex: 1;
  min-width: 0;
}

.rank__name {
  display: block;
  overflow: hidden;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank__meta {
  display: block;
  margin-top: 2px;
  overflow: hidden;
  font-size: 11px;
  color: var(--muted-2);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank__value {
  flex: none;
  font-size: 14px;
  font-weight: 700;
}

.rank__empty {
  padding: 24px 18px;
  font-size: 13px;
  color: var(--muted);
  text-align: center;
}

/* ================================================================ 研报 */
.posts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

/* ================================================================ 注册引导 */
.cta-band {
  padding: 56px 0;
  color: #e2e8f0;
  background:
    radial-gradient(600px 200px at 20% 0%, rgb(37 99 235 / 26%), transparent 70%), #0f172a;
}

.cta-band__inner {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
}

.cta-band__title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #f8fafc;
}

.cta-band__desc {
  max-width: 520px;
  margin: 8px 0 0;
  font-size: 14px;
  line-height: 1.8;
  color: #94a3b8;
}

.cta-band__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

/* ================================================================ 其它 */
.disclaimer-wrap {
  padding: 26px 0 36px;
  background: var(--bg);
  border-top: 1px solid var(--line-soft);
}

.disclaimer {
  margin: 0;
  font-size: 12px;
  line-height: 1.8;
  color: var(--muted-2);
  text-align: center;
}

.link-more {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand);
}

.link-more:hover {
  text-decoration: underline;
}

/* ================================================================ 响应式 */
@media (max-width: 1024px) {
  .hero__inner {
    grid-template-columns: 1fr;
    gap: 40px;
    padding-top: 56px;
    padding-bottom: 60px;
  }

  .hero__title {
    font-size: 42px;
  }

  .insights__grid,
  .types,
  .boards,
  .posts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .hero__title {
    font-size: 32px;
  }

  .hero__desc {
    font-size: 14px;
  }

  .hero__facts {
    gap: 24px;
  }

  .insights__grid,
  .types,
  .boards,
  .posts {
    grid-template-columns: 1fr;
  }

  .temp {
    padding: 20px;
  }

  .cta-band__inner {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
