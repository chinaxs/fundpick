<script setup lang="ts">
import type { TypeStat } from '@project/shared'

const props = defineProps<{ items: TypeStat[] }>()

const maxCount = computed(() => Math.max(...props.items.map((i) => i.count), 1))

function widthOf(count: number) {
  return `${Math.max(4, (count / maxCount.value) * 100)}%`
}

function returnTone(value: number | null) {
  if (value === null || value === 0) return ''
  return value > 0 ? 'up' : 'down'
}

function fmtReturn(value: number | null) {
  if (value === null) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}
</script>

<template>
  <div class="type-bars">
    <div v-for="item in items" :key="item.type" class="row">
      <span class="row__label">{{ item.label }}</span>

      <div class="row__track">
        <div class="row__fill" :style="{ width: widthOf(item.count) }" />
      </div>

      <span class="row__count num">{{ item.count.toLocaleString() }}</span>
      <span class="row__ret num" :class="returnTone(item.avg_return)">
        {{ fmtReturn(item.avg_return) }}
      </span>
    </div>

    <p class="legend">条长表示基金数量，右侧为该类型近 1 年平均收益</p>
  </div>
</template>

<style scoped>
.type-bars {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.row {
  display: grid;
  grid-template-columns: 68px 1fr 72px 82px;
  gap: 14px;
  align-items: center;
  padding: 9px 0;
}

.row__label {
  font-size: 14px;
  color: var(--ink-2);
}

.row__track {
  height: 26px;
  overflow: hidden;
  background: var(--bg-soft);
  border-radius: 6px;
}

.row__fill {
  height: 100%;
  background: linear-gradient(90deg, #dbeafe, #93c5fd);
  border-radius: 6px;
  transition: width 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}

.row__count {
  font-size: 14px;
  color: var(--ink);
  text-align: right;
}

.row__ret {
  font-size: 14px;
  font-weight: 600;
  text-align: right;
}

.up {
  color: var(--up);
}

.down {
  color: var(--down);
}

.legend {
  margin: 14px 0 0;
  font-size: 12px;
  color: var(--muted-2);
}

@media (max-width: 560px) {
  .row {
    grid-template-columns: 58px 1fr 66px;
  }

  .row__ret {
    display: none;
  }
}
</style>
