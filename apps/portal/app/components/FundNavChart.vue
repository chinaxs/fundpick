<script setup lang="ts">
import type { NavPoint } from '@project/shared'

/**
 * 净值曲线：手写 SVG。
 * 只有"一条折线 + 面积填充"的需求，引入 ECharts/Chart.js（数百 KB）不划算，
 * 30 行 SVG 足够且零依赖。若后续要做多基金对比、缩放、tooltip，再换图表库。
 */
const props = withDefaults(defineProps<{ points: NavPoint[]; height?: number }>(), {
  height: 240,
})

const WIDTH = 720
const PAD = 10

const geometry = computed(() => {
  const points = props.points
  if (points.length < 2) return null

  const values = points.map((p) => p.unit_nav)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const innerH = props.height - PAD * 2
  const stepX = (WIDTH - PAD * 2) / (points.length - 1)

  const coords = values.map((value, index) => ({
    x: PAD + index * stepX,
    y: PAD + (1 - (value - min) / span) * innerH,
  }))

  const first = coords[0]
  const last = coords[coords.length - 1]
  if (!first || !last) return null

  const line = coords
    .map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x.toFixed(2)},${c.y.toFixed(2)}`)
    .join(' ')

  return {
    line,
    area: `${line} L${last.x.toFixed(2)},${props.height - PAD} L${first.x.toFixed(2)},${
      props.height - PAD
    } Z`,
    min: min.toFixed(4),
    max: max.toFixed(4),
    rising: (values[values.length - 1] ?? 0) >= (values[0] ?? 0),
    start: points[0]?.nav_date ?? '',
    end: points[points.length - 1]?.nav_date ?? '',
  }
})

const strokeColor = computed(() => (geometry.value?.rising ? '#c53030' : '#2f855a'))
</script>

<template>
  <div class="chart-wrap">
    <div v-if="!geometry" class="chart-empty">暂无净值数据</div>

    <template v-else>
      <svg
        class="chart"
        :viewBox="`0 0 ${WIDTH} ${height}`"
        preserveAspectRatio="none"
        role="img"
        aria-label="净值走势"
      >
        <defs>
          <linearGradient id="navFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" :stop-color="strokeColor" stop-opacity="0.18" />
            <stop offset="100%" :stop-color="strokeColor" stop-opacity="0" />
          </linearGradient>
        </defs>
        <path :d="geometry.area" fill="url(#navFill)" />
        <path :d="geometry.line" fill="none" :stroke="strokeColor" stroke-width="2" />
      </svg>

      <div class="chart-axis">
        <span>{{ geometry.start }}</span>
        <span class="chart-range">区间 {{ geometry.min }} ~ {{ geometry.max }}</span>
        <span>{{ geometry.end }}</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.chart-wrap {
  padding: 12px 0 0;
}

.chart {
  width: 100%;
  height: auto;
  display: block;
}

.chart-empty {
  padding: 56px;
  font-size: 14px;
  color: var(--color-text-muted);
  text-align: center;
  background: var(--color-bg-soft);
  border-radius: var(--radius);
}

.chart-axis {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
  font-size: 12px;
  color: #a0aec0;
}

.chart-range {
  font-variant-numeric: tabular-nums;
}
</style>
