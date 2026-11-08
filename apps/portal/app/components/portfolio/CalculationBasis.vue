<script setup lang="ts">
const props = defineProps<{ basis: Record<string, unknown> }>()
const rules = computed(() =>
  Array.isArray(props.basis.fee_rules)
    ? (props.basis.fee_rules as {
        condition?: string
        rate?: string
        rate_type?: string
        shares?: string
        days?: number
        date_basis?: string
      }[])
    : [],
)
const source = computed(() =>
  typeof props.basis.source_url === 'string' &&
  props.basis.source_url.startsWith('https://fundf10.eastmoney.com/')
    ? props.basis.source_url
    : null,
)
</script>
<template>
  <details class="fee-basis">
    <summary>查看费用依据</summary>
    <div v-for="(rule, index) in rules" :key="index">
      <span>{{ rule.rate_type }} {{ rule.rate }}</span
      ><small
        >{{ rule.condition
        }}{{ rule.shares ? ` · ${rule.shares}份 · 持有${rule.days}天` : '' }}</small
      ><small v-if="rule.date_basis">持有期起点：{{ rule.date_basis }}</small>
    </div>
    <a v-if="source" :href="source" target="_blank" rel="noopener noreferrer">查看公开费率表 ↗</a
    ><small>当前公开费率可能与历史或平台优惠不同。</small>
  </details>
</template>
<style scoped>
.fee-basis {
  margin-top: 5px;
  font-size: 11px;
  min-width: 140px;
  max-width: 230px;
  color: var(--muted);
}
.fee-basis > summary {
  cursor: pointer;
  color: var(--brand);
}
.fee-basis > div {
  padding: 7px 0;
  border-bottom: 1px solid var(--line-soft);
}
.fee-basis small {
  display: block;
  line-height: 1.7;
  margin-top: 4px;
}
.fee-basis a {
  display: inline-block;
  color: var(--brand);
  margin-top: 7px;
}
</style>
