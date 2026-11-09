<script setup lang="ts">
import type { FundPeriod } from '@project/shared'
import { ElMessage } from 'element-plus'
const { isLoggedIn, displayName, openAuth, ensureSession } = useAuth()
await ensureSession()
const { codes: favoriteCodes, pending: favoritePending } = useFavorites()
const period = ref<FundPeriod>('1y')
const { data, pending, error, refresh } = await useDashboard(period)
watch([() => [...favoriteCodes.value].sort().join(','), favoritePending], () => {
  if (isLoggedIn.value && !favoritePending.value) refresh()
})
async function reload() {
  await refresh()
  if (error.value) ElMessage.error('刷新失败，请稍后重试')
}
useSeoMeta({
  title: '我的工作台',
  description: '查看持仓记录与收益，跟踪最近关注的基金。',
  robots: 'noindex, nofollow',
})
</script>
<template>
  <div class="workspace">
    <div class="container">
      <header class="workspace__head">
        <div>
          <h1>我的工作台</h1>
          <p class="workspace__subtitle">
            {{ isLoggedIn ? `${displayName}，查看持仓与关注动态。` : '持仓与关注，一处查看。' }}
          </p>
        </div>
        <button
          v-if="isLoggedIn"
          type="button"
          class="btn btn--ghost"
          :disabled="pending"
          @click="reload"
        >
          {{ pending ? '更新中…' : '刷新' }}
        </button>
      </header>
      <MemberNav />
      <section v-if="!isLoggedIn" class="welcome card">
        <h2>建立你的基金观察清单</h2>
        <p>登录后跟踪关注基金、记录平台买卖和查看收益。</p>
        <div class="workspace__actions">
          <button type="button" class="btn" @click="openAuth('login')">登录 / 注册</button
          ><NuxtLink to="/funds" class="text-link">先去筛选基金 →</NuxtLink>
        </div>
      </section>
      <template v-else>
        <section v-if="error" class="notice notice--error" role="alert">
          <strong>工作台加载失败</strong>
          <div class="workspace__actions">
            <button type="button" class="btn btn--ghost" :disabled="pending" @click="reload">
              重试</button
            ><button type="button" class="text-button" @click="openAuth('login')">重新登录</button>
          </div>
        </section>
        <p v-if="pending && !data" class="workspace__loading" role="status">正在加载工作台…</p>
        <template v-if="data && !error">
          <WorkspacePortfolio :summary="data.portfolio_summary" @retry="reload" />
          <WorkspaceWatchlist v-model:period="period" :data="data" :pending="pending" />
          <details v-if="data.summary.total_funds" class="workspace__analysis">
            <summary>关注结构与统计口径 <span class="block__sub">按需展开</span></summary>
            <p class="block__sub">
              {{
                pending
                  ? '更新中…'
                  : `净值最新日期 ${data.summary.latest_nav_date ?? '暂无'} · 区间收益指标覆盖 ${data.summary.metric_coverage}%`
              }}
            </p>
            <p class="block__sub">
              关注按基金只数统计，区间均值仅包含有指标的基金；风险等级与主题按规则推导。
            </p>
            <WorkspaceDistributions v-if="!pending" :data="data" />
          </details>
          <p class="disclaimer">
            持仓按用户录入的外部平台回执记录，收益与关注基金的历史区间表现分别统计。
          </p>
        </template>
      </template>
    </div>
  </div>
</template>
<style src="~/assets/css/workspace.css"></style>
<style src="~/assets/css/workspace-charts.css"></style>
