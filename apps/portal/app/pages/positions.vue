<script setup lang="ts">
const { isLoggedIn, openAuth, ensureSession } = useAuth()
await ensureSession()
const route = useRoute()
const { open: openTrade } = useTradeDialog()
const {
  view,
  page,
  pageSize,
  filters,
  portfolio,
  history,
  applications: applicationState,
  refreshing,
  actionBusy,
  reload,
  reset,
  cancelApplication,
  voidRecord,
  removeRecord,
} = await usePositionBook()
const { data, pending, error } = portfolio
const { data: trades, pending: tradesPending, error: tradesError, refresh: refreshTrades } = history
const {
  data: applications,
  error: applicationsError,
  refresh: refreshApplications,
} = applicationState
watch(
  [() => route.query.buy, isLoggedIn],
  ([code, loggedIn]) => {
    if (loggedIn && typeof code === 'string' && /^\d{6}$/.test(code))
      openTrade({ kind: 'buy', code })
  },
  { immediate: true },
)
useSeoMeta({
  title: '持仓与交易记录',
  description: '记录外部平台买卖，自动计算入账，并按基金、状态和日期查询交易流水。',
  robots: 'noindex, nofollow',
})
</script>
<template>
  <div class="trading">
    <div class="container">
      <header class="p-head">
        <div>
          <p class="section__eyebrow">PORTFOLIO & TRANSACTIONS</p>
          <h1>持仓与交易记录</h1>
          <p class="p-note">记下买卖，自动等待入账，随时查询记录。</p>
        </div>
        <div v-if="isLoggedIn" class="p-actions">
          <button
            type="button"
            class="btn btn--ghost"
            :disabled="pending || refreshing"
            @click="reload"
          >
            {{ refreshing ? '更新中…' : '刷新' }}</button
          ><button type="button" class="btn" @click="openTrade({ kind: 'buy' })">+ 买入</button>
        </div>
      </header>
      <MemberNav />
      <section v-if="!isLoggedIn" class="p-card p-empty">
        <h2>登录后建立你的交易账本</h2>
        <p>只填时间与金额，自动查询对应净值和交易费用。</p>
        <button type="button" class="btn" @click="openAuth('login')">登录 / 注册</button>
      </section>
      <template v-else>
        <div v-if="error" class="p-error" role="alert">
          组合加载失败。<button type="button" class="p-link" @click="reload">重试</button>
        </div>
        <p v-else-if="pending && !data" role="status">正在整理持仓与流水…</p>
        <template v-if="data && !error">
          <p v-if="applicationsError" class="p-error">
            待入账记录加载失败。<button type="button" class="p-link" @click="refreshApplications()">
              重试
            </button>
          </p>
          <PortfolioApplications
            :items="applications ?? []"
            :busy="actionBusy"
            @record="openTrade"
            @cancel="cancelApplication"
          />
          <PortfolioMetrics :summary="data.summary" />
          <div class="p-tabs portfolio-tabs" aria-label="持仓与交易视图">
            <button type="button" :aria-pressed="view === 'holdings'" @click="view = 'holdings'">
              我的持仓</button
            ><button type="button" :aria-pressed="view === 'history'" @click="view = 'history'">
              交易记录
            </button>
          </div>
          <PortfolioHoldings v-if="view === 'holdings'" :items="data.holdings" @trade="openTrade" />
          <details
            v-if="data.legacy_positions.length"
            id="legacy-review"
            class="legacy-fold"
            :open="route.hash === '#legacy-review'"
          >
            <summary>{{ data.legacy_positions.length }} 笔旧持仓待核对</summary>
            <PortfolioLegacy :items="data.legacy_positions" @migrate="openTrade" />
          </details>
        </template>
        <PortfolioHistory
          v-if="view === 'history'"
          :data="trades"
          :pending="tradesPending"
          :failed="!!tradesError"
          :page="page"
          :page-size="pageSize"
          :busy="actionBusy"
          @page="page = $event"
          @page-size="pageSize = $event"
          @retry="refreshTrades()"
          @cancel="cancelApplication"
          @void="voidRecord"
          @remove="removeRecord"
          ><PortfolioHistoryFilters v-model="filters" @reset="reset"
        /></PortfolioHistory>
        <div class="portfolio-more">
          <NuxtLink to="/portfolio/tools">已有持仓、分红与转换等更多操作 →</NuxtLink>
        </div>
        <details class="portfolio-help">
          <summary>记账说明</summary>
          <p class="p-note">
            买入填金额，卖出填份额，系统按下单时间查询净值与费用。净值未公布时自动等待；平台实际结果有差异时可核对调整。本站只记账，撤销或作废记录不会操作外部平台的交易。
          </p>
        </details>
      </template>
    </div>
  </div>
</template>
<style src="~/assets/css/portfolio.css"></style>
<style src="~/assets/css/trade-history.css"></style>
