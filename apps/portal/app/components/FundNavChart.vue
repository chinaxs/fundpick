<script setup lang="ts">
import type { NavPoint } from '@project/shared'

/**
 * 净值曲线：手写 SVG。
 * 只有"折线 + 面积 + 悬浮读数"的需求，引入 ECharts（数百 KB）不划算。
 * 若后续要做多基金对比、区间缩放、K 线，再换图表库。
 */
const props = withDefaults(defineProps<{ points: NavPoint[]; height?: number }>(), {
  height: 280,
})

const WIDTH = 760
const PAD = { top: 16, right: 12, bottom: 26, left: 52 }

const svgRef = ref<SVGSVGElement | null>(null)
const hoverIndex = ref<number | null>(null)

const geometry = computed(() => {
  const points = props.points
  if (points.length < 2) return null

  const values = points.map((p) => p.unit_nav)
  const rawMin = Math.min(...values)
  const rawMax = Math.max(...values)
  const padding = (rawMax - rawMin) * 0.08 || 0.01
  const min = rawMin - padding
  const max = rawMax + padding
  const span = max - min || 1

  const innerW = WIDTH - PAD.left - PAD.right
  const innerH = props.height - PAD.top - PAD.bottom
  const stepX = innerW / (points.length - 1)

  const coords = values.map((value, index) => ({
    x: PAD.left + index * stepX,
    y: PAD.top + (1 - (value - min) / span) * innerH,
  }))

  const first = coords[0]
  const last = coords[coords.length - 1]
  if (!first || !last) return null

  const line = coords
    .map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x.toFixed(2)},${c.y.toFixed(2)}`)
    .join(' ')

  // Y 轴 4 条网格
  const ticks = [0, 1, 2, 3].map((i) => {
    const ratio = i / 3
    return {
      y: PAD.top + ratio * innerH,
      label: (max - ratio * span).toFixed(3),
    }
  })

  const rising = (values[values.length - 1] ?? 0) >= (values[0] ?? 0)

  return {
    line,
    area: `${line} L${last.x.toFixed(2)},${props.height - PAD.bottom} L${first.x.toFixed(
      2,
    )},${props.height - PAD.bottom} Z`,
    coords,
    ticks,
    stepX,
    rising,
    min: rawMin,
    max: rawMax,
    start: points[0]?.nav_date ?? '',
    end: points[points.length - 1]?.nav_date ?? '',
  }
})

const strokeColor = computed(() => (geometry.value?.rising ? '#dc2626' : '#059669'))

const hovered = computed(() => {
  const index = hoverIndex.value
  if (index === null || !geometry.value) return null
  const point = props.points[index]
  const coord = geometry.value.coords[index]
  if (!point || !coord) return null
  return { point, coord, leftPct: (coord.x / WIDTH) * 100 }
})

function handleMove(event: MouseEvent) {
  const svg = svgRef.value
  const geo = geometry.value
  if (!svg || !geo) return
  const rect = svg.getBoundingClientRect()
  const x = ((event.clientX - rect.left) / rect.width) * WIDTH
  const raw = Math.round((x - PAD.left) / geo.stepX)
  hoverIndex.value = Math.min(Math.max(raw, 0), props.points.length - 1)
}

function handleLeave() {
  hoverIndex.value = null
}
</script>

<template>
  <div class="chart-wrap">
    <div v-if="!geometry" class="chart-empty">暂无净值数据</div>

    <template v-else>
      <div class="chart-canvas">
        <svg
          ref="svgRef"
          class="chart"
          :viewBox="`0 0 ${WIDTH} ${height}`"
          preserveAspectRatio="none"
          role="img"
          aria-label="净值走势"
          @mousemove="handleMove"
          @mouseleave="handleLeave"
        >
          <defs>
            <linearGradient id="navFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" :stop-color="strokeColor" stop-opacity="0.16" />
              <stop offset="100%" :stop-color="strokeColor" stop-opacity="0" />
            </linearGradient>
          </defs>

          <!-- 网格与 Y 轴刻度 -->
          <g class="grid">
            <line
              v-for="tick in geometry.ticks"
              :key="tick.y"
              :x1="PAD.left"
              :x2="WIDTH - PAD.right"
              :y1="tick.y"
              :y2="tick.y"
            />
            <text
              v-for="tick in geometry.ticks"
              :key="`t-${tick.y}`"
              :x="PAD.left - 8"
              :y="tick.y + 3"
              text-anchor="end"
            >
              {{ tick.label }}
            </text>
          </g>

          <path :d="geometry.area" fill="url(#navFill)" />
          <path :d="geometry.line" fill="none" :stroke="strokeColor" stroke-width="2" />

          <!-- 悬浮指示 -->
          <g v-if="hovered">
            <line
              :x1="hovered.coord.x"
              :x2="hovered.coord.x"
              :y1="PAD.top"
              :y2="height - PAD.bottom"
              class="cursor-line"
            />
            <circle
              :cx="hovered.coord.x"
              :cy="hovered.coord.y"
              r="4"
              :fill="strokeColor"
              stroke="#fff"
              stroke-width="2"
            />
          </g>
        </svg>

        <div v-if="hovered" class="tooltip" :style="{ left: `${hovered.leftPct}%` }">
          <span class="tooltip__date">{{ hovered.point.nav_date }}</span>
          <span class="tooltip__nav">{{ hovered.point.unit_nav.toFixed(4) }}</span>
          <span
            v-if="hovered.point.daily_return !== null"
            class="tooltip__chg"
            :class="(hovered.point.daily_return ?? 0) >= 0 ? 'up' : 'down'"
          >
            {{ (hovered.point.daily_return ?? 0) > 0 ? '+' : ''
            }}{{ hovered.point.daily_return?.toFixed(2) }}%
          </span>
        </div>
      </div>

      <div class="chart-axis">
        <span>{{ geometry.start }}</span>
        <span class="chart-range num">
          区间 {{ geometry.min.toFixed(4) }} ~ {{ geometry.max.toFixed(4) }}
        </span>
        <span>{{ geometry.end }}</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.chart-wrap {
  padding-top: 4px;
}

.chart-canvas {
  position: relative;
}

.chart {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
  cursor: crosshair;
}

.grid line {
  stroke: var(--line-soft);
  stroke-width: 1;
  stroke-dasharray: 3 3;
}

.grid text {
  font-family: var(--font-num);
  font-size: 10px;
  fill: var(--muted-2);
}

.cursor-line {
  stroke: #94a3b8;
  stroke-width: 1;
  stroke-dasharray: 3 3;
}

.tooltip {
  position: absolute;
  top: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  font-size: 12px;
  white-space: nowrap;
  pointer-events: none;
  background: rgb(15 23 42 / 92%);
  border-radius: 8px;
  transform: translateX(-50%);
  box-shadow: var(--shadow-md);
}

.tooltip__date {
  color: #94a3b8;
}

.tooltip__nav {
  font-family: var(--font-num);
  font-size: 15px;
  font-weight: 600;
  color: #fff;
}

.tooltip__chg {
  font-family: var(--font-num);
  font-size: 12px;
}

.tooltip__chg.up {
  color: #fca5a5;
}

.tooltip__chg.down {
  color: #6ee7b7;
}

.chart-axis {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  font-size: 12px;
  color: var(--muted-2);
}

.chart-range {
  color: var(--muted);
}

.chart-empty {
  padding: 64px;
  font-size: 14px;
  color: var(--muted);
  text-align: center;
  background: var(--bg-soft);
  border-radius: var(--radius);
}
</style>
