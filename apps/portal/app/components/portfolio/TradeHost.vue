<script setup lang="ts">
import { ElMessage } from 'element-plus'
const { seed, close } = useTradeDialog()
const { user, authHeaders, isLoggedIn, dialogVisible } = useAuth()
const { load: loadHoldings } = useHoldingStatus()
onMounted(() => loadHoldings())
watch([() => user.value?.id, () => authHeaders.value.Authorization], () => {
  if (!authHeaders.value.Authorization) close()
  loadHoldings(true)
})
watch(dialogVisible, (visible) => {
  if (!visible && !isLoggedIn.value) close()
})
watch(
  () => user.value?.id,
  (next, previous) => {
    if (previous != null && previous !== next) close()
  },
)
async function completed(message?: string) {
  close()
  ElMessage.success(message || '交易记录已保存')
  await Promise.allSettled([
    loadHoldings(true),
    refreshNuxtData([
      `me-portfolio-${user.value?.id}`,
      `me-applications-${user.value?.id}`,
      `me-dashboard-${user.value?.id}`,
      `me-transactions-${user.value?.id}`,
    ]),
  ])
}
</script>
<template>
  <PortfolioTradeForm
    v-if="seed && isLoggedIn"
    :key="`${seed.kind}:${seed.code}:${seed.legacy_position_id ?? ''}:${seed.application_id ?? ''}`"
    :seed="seed"
    @close="close"
    @completed="completed"
  />
</template>
<style src="~/assets/css/portfolio.css"></style>
