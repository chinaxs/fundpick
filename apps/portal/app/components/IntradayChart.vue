<script setup lang="ts">
/**
 * 指数当日分时图。
 *
 * 为什么手写 SVG 而不是引图表库：
 * 需要的只是"一条线 + 均价线 + 昨收基准 + 成交量柱 + 悬停读数"，
 * ECharts 会增加 200KB 依赖，而分时图的坐标规则又非常简单
 * （x 轴固定 241 个交易分钟，y 轴以昨收为中心上下对称）。
 *
 * 两个关键实现选择：
 *
 * 1. **横向用 viewBox 拉伸，刻度文字用 HTML 叠加**。
 *    早期版本在 onMounted 里量容器宽度再算坐标，结果是水合时序一变
 *    就可能停在 SSR 的默认宽度上（窄屏右侧刻度被裁掉）。
 *    现在曲线按 760 的逻辑宽度画、由 CSS 拉满容器，文字则完全交给 HTML，
 *    所以任何宽度都不会变形，也不需要等 JS。
 *
 * 2. **x 轴按交易分钟排布**，11:30 和 13:00 之间不留空档，
 *    否则午休会在图上留下一段很长的水平直线——A 股分时图都是这么处理的。
 */
import type { IndexMinutePoint } from '@project/shared'
import { fmtAmountCN, fmtPoint } from '@project/shared'

const props = withDefaults(
  defineProps<{
    points: IndexMinutePoint[]
    prevClose: number | null
    height?: number
  }>(),
  { height: 326, prevClose: null },
)

/** 逻辑坐标系宽度：只影响图形本身，实际宽度由 CSS 决定 */
const VB_W = 760
const SLOTS = 241 // 09:30–11:30（121）+ 13:00–15:00（120）
const PAD_L = 12
const PAD_R = 58 // 右侧留给点位刻度
const PAD_T = 14
const PAD_B = 22
const VOL_H = 40
const VOL_GAP = 12

const wrap = ref<HTMLElement | null>(null)
const plotEl = ref<HTMLElement | null>(null)

const bars = computed(() => props.points.filter((p) => Number.isFinite(p.price)))
const hasData = computed(() => bars.value.length >= 2)

const plotW = VB_W - PAD_L - PAD_R
/** 绘图区在逻辑坐标里的右边界：viewBox 到此为止，右侧 58px 由独立刻度栏承担 */
const plotEnd = PAD_L + plotW
const plotH = computed(() => Math.max(80, props.height - PAD_T - PAD_B - VOL_H - VOL_GAP))
const volTop = computed(() => PAD_T + plotH.value + VOL_GAP)
const step = plotW / (SLOTS - 1)

/** 昨收：优先用服务端给的，缺失时退化成第一个点（此时曲线平在中线上） */
const base = computed(() => props.prevClose ?? bars.value[0]?.price ?? 0)

/** y 轴以昨收为中心对称，涨跌幅度在视觉上可比 */
const range = computed(() => {
  const values = bars.value.map((p) => p.price)
  if (!values.length || !base.value) return { min: 0, max: 1 }
  const maxDev = Math.max(...values.map((v) => Math.abs(v - base.value)), 0.01) * 1.12
  return { min: base.value - maxDev, max: base.value + maxDev }
})

const maxVolume = computed(() => Math.max(...bars.value.map((p) => p.volume ?? 0), 1))

function xOf(index: number): number {
  return PAD_L + index * step
}

function yOf(value: number): number {
  const { min, max } = range.value
  const ratio = max === min ? 0.5 : (max - value) / (max - min)
  return PAD_T + ratio * plotH.value
}

function linePath(key: 'price' | 'avg_price'): string {
  const parts: string[] = []
  bars.value.forEach((bar, index) => {
    const value = key === 'price' ? bar.price : bar.avg_price
    if (value == null || !Number.isFinite(value)) return
    parts.push(`${parts.length ? 'L' : 'M'}${xOf(index).toFixed(2)},${yOf(value).toFixed(2)}`)
  })
  return parts.join(' ')
}

const pricePath = computed(() => linePath('price'))
const avgPath = computed(() => linePath('avg_price'))

const areaPath = computed(() => {
  if (!pricePath.value) return ''
  const lastIndex = bars.value.length - 1
  const floor = PAD_T + plotH.value
  return `${pricePath.value} L${xOf(lastIndex).toFixed(2)},${floor} L${xOf(0).toFixed(2)},${floor} Z`
})

const tone = computed<'up' | 'down' | 'neutral'>(() => {
  const last = bars.value[bars.value.length - 1]
  if (!last || !base.value) return 'neutral'
  if (last.price > base.value) return 'up'
  if (last.price < base.value) return 'down'
  return 'neutral'
})

/** 网格刻度：上、上 1/4、昨收、下 1/4、下 */
const gridLines = computed(() => {
  const { min, max } = range.value
  const rows = [max, max - (max - min) * 0.25, base.value, min + (max - min) * 0.25, min]
  return rows.map((price, index) => ({
    price,
    y: yOf(price),
    isBase: index === 2,
    pct: base.value ? ((price - base.value) / base.value) * 100 : null,
  }))
})

const volumes = computed(() =>
  bars.value.map((bar, index) => {
    const previousBar = bars.value[index - 1]
    const previous = previousBar ? previousBar.price : bar.price
    const height = ((bar.volume ?? 0) / maxVolume.value) * VOL_H
    return {
      x: xOf(index) - step * 0.34,
      y: volTop.value + VOL_H - height,
      width: Math.max(0.8, step * 0.68),
      height: Math.max(0, height),
      up: bar.price >= previous,
    }
  }),
)

const hover = ref<number | null>(null)

/**
 * 悬停定位：把鼠标位置换算回逻辑坐标。
 * 容器宽度随时可变，所以必须先按比例折算，不能直接用像素差。
 */
function locate(event: PointerEvent) {
  // 用绘图区而不是整个容器：右侧 58px 是刻度栏，不属于坐标范围
  const element = plotEl.value
  if (!element) return
  const rect = element.getBoundingClientRect()
  if (!rect.width) return
  const logicalX = ((event.clientX - rect.left) / rect.width) * plotEnd
  const index = Math.round((logicalX - PAD_L) / step)
  hover.value = Math.min(bars.value.length - 1, Math.max(0, index))
}

const tip = computed(() => {
  if (hover.value == null) return null
  const bar = bars.value[hover.value]
  if (!bar) return null
  const x = xOf(hover.value)
  return {
    bar,
    x,
    y: yOf(bar.price),
    pct: base.value ? ((bar.price - base.value) / base.value) * 100 : null,
    /** 逻辑坐标换成百分比，避免依赖测量宽度 */
    left: `${(x / plotEnd) * 100}%`,
    flip: x > plotEnd * 0.62,
  }
})

const yLabels = computed(() =>
  gridLines.value.map((line) => ({
    key: line.price,
    text: fmtPoint(line.price),
    top: `${line.y}px`,
    isBase: line.isBase,
  })),
)

/** 三个时间刻度：起点、午休中点、终点（对齐 plot 区左右边界） */
const xLabels = computed(() => [
  { text: '09:30', left: `${(xOf(0) / plotEnd) * 100}%`, anchor: 'translateX(0)' },
  {
    text: '11:30 / 13:00',
    left: `${(xOf((SLOTS - 1) / 2) / plotEnd) * 100}%`,
    anchor: 'translateX(-50%)',
  },
  { text: '15:00', left: `${(xOf(SLOTS - 1) / plotEnd) * 100}%`, anchor: 'translateX(-100%)' },
])
</script>

<template>
  <div
    ref="wrap"
    class="chart"
    :style="{ height: `${height}px` }"
    @pointermove="locate"
    @pointerdown="locate"
    @pointerleave="hover = null"
  >
    <div ref="plotEl" class="chart__plot">
      <svg
        v-if="hasData"
        class="chart__svg"
        :viewBox="`0 0 ${plotEnd} ${height}`"
        preserveAspectRatio="none"
        :height="height"
        role="img"
        aria-label="指数当日分时走势"
      >
        <line
          v-for="line in gridLines"
          :key="`g-${line.price}`"
          :x1="PAD_L"
          :x2="plotEnd"
          :y1="line.y"
          :y2="line.y"
          class="chart__grid"
          :class="{ 'is-base': line.isBase }"
          vector-effect="non-scaling-stroke"
        />

        <path :d="areaPath" class="chart__area" :class="tone" />
        <path :d="avgPath" class="chart__avg" vector-effect="non-scaling-stroke" />
        <path
          :d="pricePath"
          class="chart__price"
          :class="tone"
          vector-effect="non-scaling-stroke"
        />

        <rect
          v-for="(bar, index) in volumes"
          :key="`v-${index}`"
          :x="bar.x"
          :y="bar.y"
          :width="bar.width"
          :height="bar.height"
          class="chart__vol"
          :class="bar.up ? 'up' : 'down'"
        />

        <line
          v-if="tip"
          :x1="tip.x"
          :x2="tip.x"
          :y1="PAD_T"
          :y2="volTop + VOL_H"
          class="chart__cursor-line"
          stroke-dasharray="3 3"
          vector-effect="non-scaling-stroke"
        />
        <circle v-if="tip" :cx="tip.x" :cy="tip.y" r="3" class="chart__cursor-dot" :class="tone" />
      </svg>

      <div v-if="!hasData" class="chart__empty">
        <p>分时数据暂不可用</p>
        <span>行情源没有返回该指数的分钟数据，稍后再看。</span>
      </div>

      <!-- 横轴时间：放在绘图区内，百分比与曲线使用同一套坐标 -->
      <template v-if="hasData">
        <span
          v-for="label in xLabels"
          :key="`x-${label.text}`"
          class="label label--x"
          :style="{ left: label.left, transform: label.anchor }"
        >
          {{ label.text }}
        </span>
      </template>

      <div
        v-if="tip"
        class="tip"
        :class="{ 'tip--flip': tip.flip }"
        :style="{ left: tip.left, top: `${Math.max(6, tip.y - 12)}px` }"
      >
        <p class="tip__time">{{ tip.bar.time }}</p>
        <p class="tip__price num">{{ fmtPoint(tip.bar.price) }}</p>
        <dl class="tip__rows">
          <div>
            <dt>涨跌</dt>
            <dd class="num" :class="(tip.pct ?? 0) > 0 ? 'up' : (tip.pct ?? 0) < 0 ? 'down' : ''">
              {{ tip.pct == null ? '—' : `${tip.pct > 0 ? '+' : ''}${tip.pct.toFixed(2)}%` }}
            </dd>
          </div>
          <div>
            <dt>均价</dt>
            <dd class="num">{{ fmtPoint(tip.bar.avg_price) }}</dd>
          </div>
          <div>
            <dt>成交额</dt>
            <dd class="num">{{ fmtAmountCN(tip.bar.amount) }}</dd>
          </div>
        </dl>
      </div>
    </div>

    <!-- 纵轴刻度：固定 58px 的独立栏，窄屏也不会被曲线压住 -->
    <div v-if="hasData" class="chart__axis">
      <span
        v-for="label in yLabels"
        :key="`y-${label.key}`"
        class="label label--y"
        :class="{ 'is-base': label.isBase }"
        :style="{ top: label.top }"
      >
        {{ label.text }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.chart {
  position: relative;
  width: 100%;
  overflow: hidden;
  touch-action: pan-y;
}

.chart__plot {
  position: absolute;
  inset: 0 58px 0 0;
}

.chart__axis {
  position: absolute;
  top: 0;
  right: 0;
  width: 58px;
  height: 100%;
}

.chart__svg {
  display: block;
  width: 100%;
}

.chart__grid {
  stroke: var(--line-soft);
  stroke-width: 1;
}

.chart__grid.is-base {
  stroke: var(--muted-2);
  stroke-dasharray: 4 4;
}

.chart__area {
  fill: var(--muted-2);
  opacity: 0.08;
}

.chart__area.up {
  fill: var(--up);
}

.chart__area.down {
  fill: var(--down);
}

.chart__price {
  fill: none;
  stroke: var(--muted);
  stroke-width: 1.6;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.chart__price.up {
  stroke: var(--up);
}

.chart__price.down {
  stroke: var(--down);
}

.chart__avg {
  fill: none;
  stroke: #d97706;
  stroke-width: 1.1;
  stroke-linejoin: round;
  opacity: 0.85;
}

.chart__vol {
  opacity: 0.28;
}

.chart__vol.up {
  fill: var(--up);
}

.chart__vol.down {
  fill: var(--down);
}

.chart__cursor-line {
  stroke: var(--muted-2);
  stroke-width: 1;
}

.chart__cursor-dot {
  fill: var(--muted);
  stroke: var(--bg);
  stroke-width: 1.5;
}

.chart__cursor-dot.up {
  fill: var(--up);
}

.chart__cursor-dot.down {
  fill: var(--down);
}

.label {
  position: absolute;
  font-family: var(--font-num);
  font-size: 10.5px;
  line-height: 1;
  color: var(--muted-2);
  pointer-events: none;
}

.label--y {
  right: 6px;
  transform: translateY(-50%);
}

.label--y.is-base {
  font-weight: 600;
  color: var(--muted);
}

.label--x {
  bottom: 6px;
  white-space: nowrap;
}

.chart__empty {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--muted);
  background: var(--bg-soft);
  border: 1px dashed var(--line);
  border-radius: var(--radius-sm);
}

.chart__empty p {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-2);
}

.chart__empty span {
  font-size: 12px;
}

.tip {
  position: absolute;
  z-index: 2;
  min-width: 132px;
  padding: 8px 10px;
  pointer-events: none;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md);
  transform: translate(14px, -50%);
}

.tip--flip {
  transform: translate(calc(-100% - 14px), -50%);
}

.tip__time {
  margin: 0;
  font-family: var(--font-num);
  font-size: 10.5px;
  color: var(--muted);
}

.tip__price {
  margin: 1px 0 4px;
  font-family: var(--font-num);
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
}

.tip__rows {
  display: grid;
  gap: 2px;
  margin: 0;
}

.tip__rows div {
  display: flex;
  gap: 10px;
  justify-content: space-between;
  font-size: 11px;
}

.tip__rows dt {
  color: var(--muted-2);
}

.tip__rows dd {
  margin: 0;
  font-family: var(--font-num);
  color: var(--ink-2);
}

.tip__rows dd.up {
  color: var(--up);
}

.tip__rows dd.down {
  color: var(--down);
}
</style>
