<script setup lang="ts">
import type { NuxtError } from '#app'

const props = defineProps<{ error: NuxtError }>()

const isNotFound = computed(() => props.error.statusCode === 404)

useSeoMeta({ title: isNotFound.value ? '页面不存在' : '出错了' })
</script>

<template>
  <div class="error">
    <div class="error__code">{{ error.statusCode }}</div>
    <h1 class="error__title">{{ isNotFound ? '页面走丢了' : '服务暂时不可用' }}</h1>
    <p class="error__desc">{{ error.statusMessage || '请稍后重试' }}</p>
    <NuxtLink to="/" class="btn">返回首页</NuxtLink>
  </div>
</template>

<style scoped>
.error {
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 12px;
  min-height: 100vh;
  padding: 24px;
  text-align: center;
}

.error__code {
  font-size: 88px;
  font-weight: 800;
  line-height: 1;
  color: var(--color-primary);
  opacity: 0.2;
}

.error__title {
  margin: 0;
  font-size: 26px;
}

.error__desc {
  margin: 0 0 12px;
  color: var(--color-text-muted);
}
</style>
