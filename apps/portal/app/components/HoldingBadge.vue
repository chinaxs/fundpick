<script setup lang="ts">
defineProps<{ code: string }>()
const { isHeld } = useHoldingStatus()
</script>
<template>
  <span v-if="isHeld(code)" class="holding-badge" title="已持有该基金的模拟份额">已持仓</span>
</template>
<style scoped>
.holding-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 500;
  color: var(--brand);
  background: var(--brand-soft);
  border: 1px solid var(--line);
  border-radius: 4px;
  white-space: nowrap;
  vertical-align: middle;
  line-height: 1.8;
}
.holding-badge:focus-visible {
  outline: 2px solid var(--brand);
  outline-offset: 2px;
}
</style>
