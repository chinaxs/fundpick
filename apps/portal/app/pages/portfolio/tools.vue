<script setup lang="ts">
import { ElMessage } from 'element-plus'
import type { Reconciliation } from '~/composables/usePortfolioTools'

const { isLoggedIn, openAuth, ensureSession, user } = useAuth()
await ensureSession()
const { open: openTrade } = useTradeDialog()
const { data: portfolio } = await usePortfolio()
const { reconciliation, exportCsv } = usePortfolioTools()
type Tool = 'import' | 'dividend' | 'convert_out' | 'split' | 'reconciliation'
const activeTool = ref<Tool | null>(null)
const data = ref<Reconciliation | null>(null)
const loading = ref(false)
const loadError = ref(false)
const exporting = ref(false)
const choices = [
  { key: 'import' as const, title: '添加已有持仓', hint: '填份额和成本，一笔保存' },
  { key: 'dividend' as const, title: '记录分红', hint: '现金分红或红利再投' },
  { key: 'convert_out' as const, title: '基金转换', hint: '从一只基金转到另一只' },
]

watch(
  () => user.value?.id,
  () => {
    activeTool.value = null
    data.value = null
  },
)
watch(activeTool, (tool) => {
  if (tool === 'reconciliation') void load()
})

async function selectTool(tool: Tool) {
  activeTool.value = activeTool.value === tool ? null : tool
  await nextTick()
  if (activeTool.value) {
    document.querySelector('.tools-selected')?.scrollIntoView({
      behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
      block: 'start',
    })
  }
}

async function load() {
  if (!isLoggedIn.value) return
  loading.value = true
  loadError.value = false
  const owner = user.value?.id
  try {
    const result = await reconciliation()
    if (owner === user.value?.id) data.value = result
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

async function changed() {
  data.value = null
  await Promise.allSettled([
    useHoldingStatus().load(true),
    refreshNuxtData([
      `me-portfolio-${user.value?.id}`,
      `me-dashboard-${user.value?.id}`,
      `me-transactions-${user.value?.id}`,
    ]),
  ])
}

async function handleExport() {
  exporting.value = true
  try {
    await exportCsv()
    ElMessage.success('已开始下载')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    exporting.value = false
  }
}

useSeoMeta({
  title: '更多持仓操作',
  description: '按需添加已有持仓、记录分红或基金转换。',
  robots: 'noindex, nofollow',
})
</script>

<template>
  <div class="portfolio-tools">
    <div class="container">
      <header class="tools-head">
        <div>
          <NuxtLink to="/positions" class="tools-back">← 返回我的持仓</NuxtLink>
          <h1>更多持仓操作</h1>
          <p>日常买卖只需记一笔。已有持仓、分红或转换，在这里按需补充。</p>
        </div>
      </header>
      <MemberNav />

      <section v-if="!isLoggedIn" class="tools-panel tools-empty">
        <h2>登录后记录你的持仓</h2>
        <p>买入填金额，卖出填份额，净值与费用自动查询。</p>
        <el-button type="primary" size="large" @click="openAuth('login')">登录 / 注册</el-button>
      </section>

      <template v-else>
        <section class="tools-panel tools-daily">
          <div>
            <h2>只是想记一笔买卖？</h2>
            <p>填金额或份额和下单时间，系统自动计算。</p>
          </div>
          <div class="tools-actions">
            <el-button type="primary" size="large" @click="openTrade({ kind: 'buy' })"
              >记买入</el-button
            >
            <el-button size="large" @click="openTrade({ kind: 'sell' })">记卖出</el-button>
          </div>
        </section>

        <div class="tools-choices" aria-label="补充记录类型">
          <button
            v-for="choice in choices"
            :key="choice.key"
            type="button"
            :aria-pressed="activeTool === choice.key"
            @click="selectTool(choice.key)"
          >
            <strong>{{ choice.title }}</strong
            ><span>{{ choice.hint }}</span>
          </button>
        </div>

        <div v-if="activeTool" class="tools-selected">
          <el-button link class="tools-close" @click="activeTool = null">收起 ×</el-button>
          <PortfolioImportPanel v-if="activeTool === 'import'" @imported="changed" />
          <PortfolioFlowsPanel
            v-else-if="activeTool !== 'reconciliation'"
            :key="activeTool"
            :initial-kind="activeTool"
            :holdings="portfolio?.holdings ?? []"
            @changed="changed"
          />
          <template v-else>
            <el-alert v-if="loadError" title="数据加载失败，请重试" type="error" :closable="false">
              <el-button link @click="load">重新加载</el-button>
            </el-alert>
            <PortfolioReconciliation v-else :data="data" :loading="loading" />
          </template>
        </div>

        <details class="tools-advanced">
          <summary>其他操作</summary>
          <div class="tools-actions">
            <el-button @click="selectTool('split')">记录份额拆分 / 合并</el-button>
            <el-button @click="selectTool('reconciliation')">查看收益明细</el-button>
            <el-button :loading="exporting" @click="handleExport">导出记录</el-button>
          </div>
        </details>
      </template>
    </div>
  </div>
</template>

<style src="~/assets/css/portfolio-tools.css"></style>
