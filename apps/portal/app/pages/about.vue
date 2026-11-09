<script setup lang="ts">
useSeoMeta({
  title: '关于',
  description:
    '拾贝 FundPick 是开源基金模拟交易、持仓管理与基金筛选工具，支持投资记账、净值查询和收益分析，不执行真实交易。',
})

const principles = [
  {
    title: '口径写清楚',
    detail: '区间收益与风险指标分别展示数据来源、基准日期和覆盖情况，缺失数据明确标注，方便核对。',
  },
  {
    title: '不猜数据',
    detail:
      '没有的数据就显示"—"，不做插值、不编造。风险指标只对已采集到的基金展示，未覆盖的排序时统一排在末尾。',
  },
  {
    title: '不作投资建议',
    detail:
      '我们只提供筛选与对比工具，不推荐具体产品、不承诺收益。工具能缩短找答案的时间，不能替代你自己的判断。',
  },
]

const stack = [
  { name: '门户', detail: 'Nuxt 4 · SSR' },
  { name: '后台', detail: 'Vue 3 · Element Plus' },
  { name: '服务', detail: 'FastAPI · SQLAlchemy 2.x' },
  { name: '数据', detail: 'MySQL · Alembic' },
]
</script>

<template>
  <div class="section">
    <div class="container about">
      <p class="about__eyebrow">关于</p>
      <h1 class="about__title">拾贝 FundPick</h1>
      <p class="about__lead">
        开源基金模拟交易、投资记账与持仓管理工具。记录买卖、观察收益，也可以筛选和对比基金。
        本站不执行真实交易，支持记录外部平台交易或用于模拟练习。
      </p>

      <h2 class="about__h2">我们坚持的三件事</h2>
      <div class="principles">
        <article v-for="item in principles" :key="item.title" class="principle">
          <h3 class="principle__title">{{ item.title }}</h3>
          <p class="principle__desc">{{ item.detail }}</p>
        </article>
      </div>

      <h2 class="about__h2">数据从哪来</h2>
      <p class="about__p">
        当前数据接自公开渠道，覆盖全市场公募基金的类型、规模、区间收益与风险指标。 净值口径为
        <strong>T+1</strong>：官方净值在每个交易日收盘后由基金公司计算、托管行复核，
        当晚公布。<strong>公募基金没有真正的"实时净值"</strong>，你在别处看到的盘中估值，
        是用上一季度披露的持仓倒推的模拟值，仅作参考。
      </p>
      <p class="about__p">
        数据采集中可能存在延迟或个别字段缺失，页面会如实标注而不是填补。
        如果发现明显错误，欢迎通过后台反馈。
      </p>

      <h2 class="about__h2">技术实现</h2>
      <div class="stack">
        <div v-for="item in stack" :key="item.name" class="stack__item">
          <div class="stack__name">{{ item.name }}</div>
          <div class="stack__detail">{{ item.detail }}</div>
        </div>
      </div>

      <div class="disclaimer">
        <h2 class="disclaimer__title">风险提示</h2>
        <p class="disclaimer__text">
          本站数据来自公开渠道，仅作研究参考，不构成投资建议。基金过往业绩不代表未来表现，
          基金投资有风险，决策前请阅读基金合同与招募说明书，并以基金公司公告为准。
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.about {
  max-width: 780px;
}

.about__eyebrow {
  margin: 0 0 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.about__title {
  margin: 0;
  font-size: clamp(28px, 4vw, 40px);
  letter-spacing: -0.02em;
}

.about__lead {
  margin: 16px 0 0;
  font-size: 16px;
  line-height: 1.9;
  color: var(--ink-2);
}

.about__h2 {
  margin: 48px 0 16px;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.about__p {
  margin: 0 0 14px;
  font-size: 14px;
  line-height: 1.95;
  color: var(--muted);
}

.about__p strong {
  color: var(--ink-2);
}

/* ---- 三条原则 ---- */
.principles {
  display: grid;
  gap: 14px;
}

.principle {
  padding: 20px 22px;
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.principle__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
}

.principle__desc {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.9;
  color: var(--muted);
}

/* ---- 技术栈 ---- */
.stack {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stack__item {
  padding: 16px;
  text-align: center;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
}

.stack__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}

.stack__detail {
  margin-top: 4px;
  font-size: 11px;
  color: var(--muted-2);
}

/* ---- 免责 ---- */
.disclaimer {
  margin-top: 40px;
  padding: 20px 22px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: var(--radius);
}

.disclaimer__title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #92400e;
}

.disclaimer__text {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.9;
  color: #a16207;
}

@media (max-width: 640px) {
  .stack {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
