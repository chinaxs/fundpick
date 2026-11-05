<script setup lang="ts">
/**
 * 品牌标识：贝壳 + 上升。
 *
 * 图上三层含义：
 * - 扇形贝壳轮廓 → "拾贝"（从海里捡出值得的那一枚）
 * - 中脉最长且垂直 → 净值走势的基线
 * - 底部圆点 → 珍珠，也像图表上的数据点
 *
 * 用 currentColor 填充底色，尺寸由外部控制，深色/浅色背景都能用。
 */
withDefaults(
  defineProps<{
    size?: number
  }>(),
  { size: 32 },
)
</script>

<template>
  <svg class="mark" :width="size" :height="size" viewBox="0 0 40 40" role="img" aria-label="拾贝">
    <rect width="40" height="40" rx="11" fill="currentColor" />
    <g fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" opacity="0.95">
      <!-- 贝壳顶弧 -->
      <path d="M11.6 13.8Q20 18.6 28.4 13.8" />
      <!-- 中脉 -->
      <path d="M20 29.4V11.2" />
      <!-- 左右叶 -->
      <path d="M20 29.4C20 23 16.4 17.2 11.6 13.8" />
      <path d="M20 29.4C20 23 23.6 17.2 28.4 13.8" />
    </g>
    <!-- 珍珠 / 数据点 -->
    <circle cx="20" cy="29.4" r="2.3" fill="#fff" />
  </svg>
</template>

<style scoped>
.mark {
  flex: none;
  display: block;
  overflow: visible;
}
</style>
