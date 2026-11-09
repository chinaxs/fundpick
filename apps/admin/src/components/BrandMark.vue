<script setup lang="ts">
/**
 * 品牌标识：贝壳 + 上升（与门户保持一致）。
 * 底色用 currentColor，由外部控制尺寸与颜色。
 */
withDefaults(defineProps<{ size?: number }>(), { size: 32 })
</script>

<template>
  <svg class="mark" :width="size" :height="size" viewBox="0 0 40 40" role="img" aria-label="拾贝">
    <rect width="40" height="40" rx="11" fill="currentColor" />
    <g fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" opacity="0.95">
      <path d="M11.6 13.8Q20 18.6 28.4 13.8" />
      <path d="M20 29.4V11.2" />
      <path d="M20 29.4C20 23 16.4 17.2 11.6 13.8" />
      <path d="M20 29.4C20 23 23.6 17.2 28.4 13.8" />
    </g>
    <circle cx="20" cy="29.4" r="2.3" fill="#fff" />
  </svg>
</template>

<style scoped>
.mark {
  flex: none;
  display: block;
}
</style>
