<script setup lang="ts">
import { FUND_TYPE_MAP, type FundType } from '@project/shared'

const { data: overview } = await useFundList({ page_size: 1 }, 'home-total')
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

const totalFunds = computed(() => overview.value?.total ?? 0)

const typeEntries = [
  { type: 'stock' as FundType, desc: '高风险高弹性，追求长期增值' },
  { type: 'hybrid' as FundType, desc: '股债搭配，兼顾进攻与防守' },
  { type: 'bond' as FundType, desc: '波动较小，注重稳健收益' },
  { type: 'index' as FundType, desc: '被动跟踪指数，费率更低' },
]

const boards = computed(() => [
  { title: '近 1 年收益榜', desc: '过去一年表现最好的基金', data: top1y.value, period: '1y' },
  { title: '近 3 年收益榜', desc: '穿越周期的中长期赢家', data: top3y.value, period: '3y' },
  { title: '债券型精选', desc: '低波动品类的领先者', data: bondTop.value, period: '1y' },
])

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

useSeoMeta({
  title: '基金数据分析',
  description: '覆盖全市场公募基金，按收益、回撤、夏普、规模等维度筛选对比。',
  ogTitle: 'Study 基金 · 基金数据分析',
})
</script>

<template>
  <div>
    <!-- Hero -->
    <section class="hero">
      <div class="container hero__inner">
        <span class="hero__badge">全市场公募基金 · 数据驱动</span>
        <h1 class="hero__title">用数据挑基金<br />而不是靠感觉</h1>
        <p class="hero__desc">
          覆盖
          {{ totalFunds.toLocaleString() }} 只公募基金，按收益、回撤、夏普、规模等维度筛选与对比。
          所有指标可排序、可追溯，帮助你建立自己的判断标准。
        </p>

        <div class="hero__actions">
          <NuxtLink to="/funds" class="btn">开始筛选</NuxtLink>
          <NuxtLink to="/about" class="btn btn--ghost">了解方法</NuxtLink>
        </div>

        <dl class="hero__stats">
          <div>
            <dt>覆盖基金</dt>
            <dd>{{ totalFunds.toLocaleString() }}</dd>
          </div>
          <div>
            <dt>基金公司</dt>
            <dd>215 家</dd>
          </div>
          <div>
            <dt>数据更新</dt>
            <dd>每日</dd>
          </div>
        </dl>
      </div>
    </section>

    <!-- 类型入口 -->
    <section class="section section--soft">
      <div class="container">
        <div class="section__head">
          <div>
            <h2 class="section__title">按类型浏览</h2>
            <p class="section__desc">不同类型对应不同的风险收益特征</p>
          </div>
        </div>

        <div class="entries">
          <NuxtLink
            v-for="item in typeEntries"
            :key="item.type"
            :to="{ path: '/funds', query: { type: item.type } }"
            class="entry"
          >
            <div class="entry__name">{{ FUND_TYPE_MAP[item.type] }}</div>
            <p class="entry__desc">{{ item.desc }}</p>
            <span class="entry__arrow">→</span>
          </NuxtLink>
        </div>
      </div>
    </section>

    <!-- 榜单 -->
    <section class="section">
      <div class="container">
        <div class="section__head">
          <div>
            <h2 class="section__title">排行榜</h2>
            <p class="section__desc">按区间收益排序，点击查看更多</p>
          </div>
          <NuxtLink to="/funds" class="section__more">全部基金 →</NuxtLink>
        </div>

        <div class="boards">
          <div v-for="board in boards" :key="board.title" class="board">
            <div class="board__head">
              <h3 class="board__title">{{ board.title }}</h3>
              <p class="board__desc">{{ board.desc }}</p>
            </div>

            <ol class="board__list">
              <li
                v-for="(fund, index) in board.data?.items ?? []"
                :key="fund.id"
                class="board__row"
              >
                <span class="board__rank" :class="{ 'board__rank--top': index < 3 }">
                  {{ index + 1 }}
                </span>
                <NuxtLink :to="`/funds/${fund.code}`" class="board__fund">
                  <span class="board__name">{{ fund.name }}</span>
                  <span class="board__code">{{ fund.code }}</span>
                </NuxtLink>
                <span
                  class="board__value"
                  :class="
                    (fund.return_rate ?? 0) > 0
                      ? 'board__value--up'
                      : (fund.return_rate ?? 0) < 0
                        ? 'board__value--down'
                        : ''
                  "
                >
                  {{ fmtPct(fund.return_rate) }}
                </span>
              </li>
            </ol>

            <NuxtLink
              :to="{ path: '/funds', query: { period: board.period, sort_by: 'return' } }"
              class="board__more"
            >
              查看完整榜单 →
            </NuxtLink>
          </div>
        </div>
      </div>
    </section>

    <!-- 研报 -->
    <section v-if="articles?.items?.length" class="section section--soft">
      <div class="container">
        <div class="section__head">
          <div>
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

    <section class="section">
      <div class="container">
        <p class="disclaimer">
          本站数据来源于公开渠道，可能存在延迟或误差；所有内容仅供研究参考，不构成投资建议。
          基金过往业绩不代表未来表现，投资前请阅读基金合同与招募说明书，并根据自身风险承受能力独立决策。
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  color: #fff;
  background:
    radial-gradient(900px 400px at 80% -10%, rgb(43 108 176 / 55%), transparent 60%),
    linear-gradient(160deg, #1a202c 0%, #1f3a5f 100%);
}

.hero__inner {
  padding: 96px 20px 80px;
}

.hero__badge {
  display: inline-block;
  padding: 6px 14px;
  font-size: 12px;
  letter-spacing: 0.08em;
  color: #bee3f8;
  background: rgb(255 255 255 / 8%);
  border: 1px solid rgb(255 255 255 / 14%);
  border-radius: 999px;
}

.hero__title {
  margin: 20px 0 0;
  font-size: clamp(32px, 5vw, 52px);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.hero__desc {
  max-width: 600px;
  margin: 20px 0 0;
  font-size: 16px;
  line-height: 1.9;
  color: #cbd5e0;
}

.hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 32px;
}

.hero__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 48px;
  margin: 56px 0 0;
}

.hero__stats dt {
  font-size: 13px;
  color: #a0aec0;
}

.hero__stats dd {
  margin: 4px 0 0;
  font-size: 22px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.entries {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.entry {
  position: relative;
  padding: 24px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.entry:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
}

.entry__name {
  font-size: 18px;
  font-weight: 600;
}

.entry__desc {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-text-muted);
}

.entry__arrow {
  position: absolute;
  top: 20px;
  right: 22px;
  color: var(--color-primary);
}

.boards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.board {
  display: flex;
  flex-direction: column;
  padding: 22px 24px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.board__head {
  margin-bottom: 12px;
}

.board__title {
  margin: 0;
  font-size: 17px;
}

.board__desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-muted);
}

.board__list {
  flex: 1;
  margin: 0;
  padding: 0;
  list-style: none;
}

.board__row {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 9px 0;
  border-bottom: 1px dashed var(--color-border);
}

.board__rank {
  flex: none;
  width: 20px;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: #a0aec0;
  text-align: center;
}

.board__rank--top {
  font-weight: 700;
  color: var(--color-primary);
}

.board__fund {
  display: flex;
  flex: 1;
  gap: 8px;
  align-items: baseline;
  min-width: 0;
}

.board__name {
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.board__name:hover {
  color: var(--color-primary);
}

.board__code {
  flex: none;
  font-size: 12px;
  color: #a0aec0;
}

.board__value {
  flex: none;
  font-size: 14px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.board__value--up {
  color: #c53030;
}

.board__value--down {
  color: #2f855a;
}

.board__more {
  margin-top: 14px;
  font-size: 13px;
  color: var(--color-primary);
}

.section__more {
  font-size: 14px;
  color: var(--color-primary);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
}

.disclaimer {
  font-size: 13px;
  line-height: 2;
  color: #a0aec0;
  text-align: center;
}
</style>
