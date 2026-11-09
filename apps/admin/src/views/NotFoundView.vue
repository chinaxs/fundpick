<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found">
    <h1>404</h1>
    <p>你访问的页面不存在</p>
    <el-button type="primary" @click="router.replace('/dashboard')">返回首页</el-button>
  </div>
</template>

<style scoped lang="scss">
.not-found {
  display: grid;
  place-items: center;
  gap: 12px;
  align-content: center;
  min-height: 100vh;

  h1 {
    margin: 0;
    font-size: 72px;
    color: $color-primary;
  }

  p {
    margin: 0;
    color: $text-secondary;
  }
}
</style>
