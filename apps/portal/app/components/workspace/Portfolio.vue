<script setup lang="ts">
import type { PortfolioSummary } from '@project/shared'
import { fmtPoint, toneOf } from '@project/shared'
const props = defineProps<{ summary?: PortfolioSummary | null }>()
const emit = defineEmits<{ retry: [] }>()
const visible = ref(true)
const incomplete = computed(
  () => !!props.summary && props.summary.valued_count < props.summary.count,
)
function amount(value: number | null) {
  return visible.value ? fmtPoint(value) : '••••••'
}
</script>
<template>
  <section class="portfolio card" aria-labelledby="portfolio-title">
    <div class="block__head block__head--between">
      <div class="portfolio__heading">
        <h2 id="portfolio-title" class="block__title">持仓记录</h2>
        <span v-if="summary" class="block__sub">{{ summary.count }} 只持有</span
        ><button
          v-if="summary?.transaction_count"
          type="button"
          class="text-button"
          :aria-pressed="!visible"
          @click="visible = !visible"
        >
          {{ visible ? '隐藏金额' : '显示金额' }}
        </button>
      </div>
      <NuxtLink to="/positions" class="text-link">{{
        summary ? (summary.transaction_count ? '持仓与交易 →' : '开始记录 →') : '查看持仓 →'
      }}</NuxtLink>
    </div>
    <p v-if="!summary" class="notice" role="status">
      持仓数据暂不可用，请刷新重试。<button
        type="button"
        class="text-button"
        @click="emit('retry')"
      >
        重新加载
      </button>
    </p>
    <template v-else>
      <div v-if="summary.transaction_count" class="portfolio__metrics">
        <div class="portfolio__primary">
          <span class="stat__label">当前市值（元）</span
          ><strong class="num">{{ amount(incomplete ? null : summary.total_market_value) }}</strong>
        </div>
        <div class="portfolio__metric">
          <span class="stat__label">持有收益（元）</span
          ><strong
            class="num"
            :class="visible && !incomplete ? toneOf(summary.total_profit) : ''"
            >{{ amount(incomplete ? null : summary.total_profit) }}</strong
          >
        </div>
        <div class="portfolio__metric">
          <span class="stat__label">累计收益（元）</span
          ><strong
            class="num"
            :class="visible && !incomplete ? toneOf(summary.total_return) : ''"
            >{{ amount(incomplete ? null : summary.total_return) }}</strong
          >
        </div>
      </div>
      <p v-else class="portfolio__empty">还没有交易记录，可从基金旁的“买入”开始记录。</p>
      <p v-if="summary.legacy_count" class="notice">
        <NuxtLink to="/positions#legacy-review"
          >{{ summary.legacy_count }} 笔旧持仓待核对，前往处理 →</NuxtLink
        >
      </p>
      <p v-if="incomplete" class="notice" role="status">
        {{ summary.count - summary.valued_count }} 只基金缺少可用净值，组合市值与收益暂不汇总。
      </p>
      <p v-if="summary.estimated_count" class="block__sub">
        {{ summary.estimated_count }} 笔按公开费率自动计算，实际平台结果可校准。
      </p>
      <p v-if="summary.pending_count" class="block__sub" style="color: #92400e">
        <NuxtLink to="/positions">{{ summary.pending_count }} 笔申请待平台确认 →</NuxtLink>
      </p>
      <p v-if="summary.calculated_count" class="block__sub">
        含 {{ summary.calculated_count }} 笔旧版折算，尚未核对平台回执。
      </p>
    </template>
  </section>
</template>
