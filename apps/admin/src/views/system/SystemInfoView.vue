<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { formatDateTime } from '@project/shared'

import { systemApi } from '@/api'
import type { SystemInfo } from '@/types/admin'

/** 系统信息（仅超管）：运行环境 + 数据规模，用于快速排障 */
const info = ref<SystemInfo | null>(null)
const loading = ref(true)
const timer = ref<ReturnType<typeof setInterval>>()

async function fetchInfo() {
  try {
    info.value = await systemApi.info()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchInfo()
  timer.value = setInterval(fetchInfo, 30_000)
})

onBeforeUnmount(() => {
  if (timer.value) clearInterval(timer.value)
})

function fmtUptime(seconds: number): string {
  const days = Math.floor(seconds / 86_400)
  const hours = Math.floor((seconds % 86_400) / 3_600)
  const minutes = Math.floor((seconds % 3_600) / 60)
  if (days) return `${days} 天 ${hours} 小时 ${minutes} 分`
  if (hours) return `${hours} 小时 ${minutes} 分`
  return `${minutes} 分`
}

/** 表行数总和，衡量数据规模 */
const totalRows = computed(() =>
  (info.value?.tables ?? []).reduce((sum, t) => sum + t.rows, 0).toLocaleString('zh-CN'),
)

const envTag = computed(() => {
  if (!info.value) return { text: '—', type: 'info' as const }
  if (info.value.debug) return { text: 'Debug 模式（禁止生产使用）', type: 'danger' as const }
  if (info.value.environment === 'production')
    return { text: 'Production', type: 'success' as const }
  return { text: info.value.environment, type: 'warning' as const }
})

function sortByRows(a: { rows: number }, b: { rows: number }): number {
  return a.rows - b.rows
}
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">系统信息</h2>
      <span class="muted">每 30 秒自动刷新</span>
    </div>

    <div class="card">
      <h3 class="section-title">运行环境</h3>
      <el-skeleton v-if="loading" :rows="4" animated />
      <el-descriptions v-else :column="2" border>
        <el-descriptions-item label="应用">{{ info?.app_name }}</el-descriptions-item>
        <el-descriptions-item label="版本">
          <el-tag size="small" effect="plain">v{{ info?.version }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="环境">
          <el-tag :type="envTag.type" size="small">{{ envTag.text }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Python">{{ info?.python_version }}</el-descriptions-item>
        <el-descriptions-item label="数据库">{{ info?.database }}</el-descriptions-item>
        <el-descriptions-item label="进程启动时间">
          {{ formatDateTime(info?.started_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="已运行">
          {{ info ? fmtUptime(info.uptime_seconds) : '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="业务表合计">{{ totalRows }} 行</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="card">
      <h3 class="section-title">数据表规模</h3>
      <el-skeleton v-if="loading" :rows="6" animated />
      <el-table v-else :data="info?.tables ?? []" size="small" stripe border>
        <el-table-column prop="name" label="表名" min-width="180" />
        <el-table-column label="行数" width="120" sortable :sort-method="sortByRows">
          <template #default="{ row }">{{ row.rows.toLocaleString('zh-CN') }}</template>
        </el-table-column>
        <el-table-column prop="comment" label="说明" min-width="260">
          <template #default="{ row }">{{ row.comment ?? '—' }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped lang="scss">
.muted {
  font-size: 13px;
  color: $text-secondary;
}

.section-title {
  margin: 0 0 16px;
  font-size: 15px;
  font-weight: 600;
}
</style>
