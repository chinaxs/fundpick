<script setup lang="ts">
import type { DistributionBucket } from '@project/shared'

const props = withDefaults(
  defineProps<{
    buckets: DistributionBucket[]
    /** 图表高度（px） */
    height?: number
    /** 紧凑模式：不显示数量标签，用于首屏小图 */
    compact?: boolean
  }>(),
  { height: 168, compact: false },
)

const maxCount = computed(() => Math.max(...props.buckets.map((b) => b.count), 1))

function isNegative(label: string) {
  return label.startsWith('-') || label.startsWith('<')
}

function barHeight(count: number) {
  const ratio = count / maxCount.value
  return `${Math.max(2, ratio * 100)}%`
}
</script>

<template>
  <div class="hist" :class="{ 'hist--compact': compact }">
    <div class="hist__bars" :style="{ height: `${height}px` }">
      <div v-for="bucket in buckets" :key="bucket.label" class="col">
        <span v-if="!compact" class="col__count num">{{ bucket.count.toLocaleString() }}</span>
        <div
          class="col__bar"
          :class="isNegative(bucket.label) ? 'col__bar--down' : 'col__bar--up'"
          :style="{ height: barHeight(bucket.count) }"
        />
      </div>
    </div>

    <div class="hist__labels">
      <span v-for="bucket in buckets" :key="bucket.label" class="label">
        {{ bucket.label }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.hist {
  width: 100%;
}

.hist__bars {
  display: flex;
  gap: 6px;
  align-items: flex-end;
}

.col {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  align-items: center;
  justify-content: flex-end;
  height: 100%;
  min-width: 0;
}

.col__count {
  font-size: 11px;
  color: var(--muted-2);
  white-space: nowrap;
}

.col__bar {
  width: 100%;
  border-radius: 4px 4px 2px 2px;
  transition: height 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}

.col__bar--up {
  background: linear-gradient(180deg, #f87171, #dc2626);
}

.col__bar--down {
  background: linear-gradient(180deg, #34d399, #059669);
}

.hist__labels {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.label {
  flex: 1;
  overflow: hidden;
  font-size: 11px;
  color: var(--muted-2);
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 紧凑模式：更细的间距与更淡的标签，用于首屏卡片 */
.hist--compact .hist__bars {
  gap: 3px;
}

.hist--compact .hist__labels {
  gap: 3px;
  margin-top: 6px;
}

.hist--compact .label {
  font-size: 9px;
}
</style>
