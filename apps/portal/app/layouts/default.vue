<script setup lang="ts">
const auth = useAuth()

// SSR 阶段即恢复登录态：有 cookie 时服务端就带上用户信息，
// 首屏直接渲染已登录状态，避免水合后闪一下。
await auth.ensureSession()
</script>

<template>
  <div class="layout">
    <AppHeader />
    <main>
      <slot />
    </main>
    <AppFooter />

    <!-- 全局单例：任意页面调用 useAuth().openAuth() 即可唤起 -->
    <AuthDialog />
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

main {
  flex: 1;
}
</style>
