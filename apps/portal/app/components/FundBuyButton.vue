<script setup lang="ts">
const props = defineProps<{
  code: string
  name?: string
  navDate?: string | null
  compact?: boolean
}>()
const { isHeld } = useHoldingStatus()
const { open } = useTradeDialog()
const held = computed(() => isHeld(props.code))
</script>
<template>
  <button
    type="button"
    class="fund-buy"
    :class="{ 'fund-buy--compact': compact }"
    :aria-label="`${held ? '加仓' : '买入'}${name ?? code}，记录平台交易`"
    title="记录其他平台的交易"
    @click="open({ kind: 'buy', code, name })"
  >
    {{ held ? '加仓' : '买入' }}
  </button>
</template>
<style scoped>
.fund-buy {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 6px 16px;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  color: var(--brand);
  background: var(--brand-soft);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  cursor: pointer;
  white-space: nowrap;
}
.fund-buy:hover {
  border-color: var(--brand);
}
.fund-buy:focus-visible {
  outline: 2px solid var(--brand);
  outline-offset: 3px;
}
.fund-buy--compact {
  min-height: 30px;
  padding: 4px 10px;
  font-size: 12px;
}
</style>
