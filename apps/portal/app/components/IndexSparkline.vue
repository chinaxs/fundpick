<script setup lang="ts">
/**
 * 迷你走势图（sparkline）：只表达趋势方向，不标刻度。
 *
 * 用 viewBox + preserveAspectRatio="none" 让图形铺满容器，再配合
 * vector-effect 让线宽不被拉伸——否则窄容器里的线会细得看不见。
 */
const props = withDefaults(
  defineProps<{
    points: number[]
    tone?: 'up' | 'down' | 'neutral'
    height?: number
  }>(),
  { tone: 'neutral', height: 40 },
)

const VIEW_W = 100
const VIEW_H = 32
const PAD = 2

const path = computed(() => {
  const values = props.points.filter((n) => Number.isFinite(n))
  if (values.length < 2) return ''

  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const step = (VIEW_W - PAD * 2) / (values.length - 1)
  const usable = VIEW_H - PAD * 2

  return values
    .map((value, index) => {
      const x = PAD + index * step
      const y = PAD + (1 - (value - min) / span) * usable
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')
})

const areaPath = computed(() =>
  path.value ? `${path.value} L${VIEW_W - PAD},${VIEW_H} L${PAD},${VIEW_H} Z` : '',
)
</script>

<template>
  <svg
    class="spark"
    :class="tone"
    :viewBox="`0 0 ${VIEW_W} ${VIEW_H}`"
    :style="{ height: `${height}px` }"
    preserveAspectRatio="none"
    aria-hidden="true"
  >
    <path v-if="areaPath" :d="areaPath" class="spark__area" />
    <path v-if="path" :d="path" class="spark__line" vector-effect="non-scaling-stroke" />
  </svg>
</template>

<style scoped>
.spark {
  display: block;
  width: 100%;
  overflow: visible;
}

.spark__line {
  fill: none;
  stroke: var(--muted-2);
  stroke-width: 1.4;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.spark__area {
  fill: var(--muted-2);
  opacity: 0.08;
}

.spark.up .spark__line {
  stroke: var(--up);
}

.spark.up .spark__area {
  fill: var(--up);
}

.spark.down .spark__line {
  stroke: var(--down);
}

.spark.down .spark__area {
  fill: var(--down);
}
</style>
