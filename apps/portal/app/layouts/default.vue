<script setup lang="ts">
import zhCn from 'element-plus/es/locale/lang/zh-cn'
const auth = useAuth()
const route = useRoute()

// 行情推送在全站建立一条连接：大盘页不显示指数条，但同样需要实时数据，
// 所以订阅放在布局而不是指数条组件里。
useMarketStream()

// SSR 阶段即恢复登录态：有 cookie 时服务端就带上用户信息，
// 首屏直接渲染已登录状态，避免水合后闪一下。
await auth.ensureSession()
onMounted(() => useHoldingStatus().load())

// 大盘列表与单指数详情都有自己的行情头部，再挂一条指数条只会重复
const showTicker = computed(() => !route.path.startsWith('/market'))
</script>

<template>
  <el-config-provider :locale="zhCn">
    <div class="layout">
      <AppHeader />
      <MarketTicker v-if="showTicker" />
      <main>
        <slot />
      </main>
      <AppFooter />

      <!-- 全局单例：任意页面调用 useAuth().openAuth() 即可唤起 -->
      <AuthDialog />
      <PortfolioTradeHost />
    </div>
  </el-config-provider>
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
