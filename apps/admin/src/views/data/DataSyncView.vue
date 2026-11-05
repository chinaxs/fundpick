<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { formatDate } from '@project/shared'

import { fundApi } from '@/api'
import type { SyncStatus } from '@/types/admin'

/** 采集监控：当前只有聚合指标，后续接入 sync_jobs 表后展示任务历史 */
const status = ref<SyncStatus | null>(null)
const loading = ref(true)
const lastCheckedAt = ref('')
const timer = ref<ReturnType<typeof setInterval>>()

async function fetchStatus() {
  try {
    status.value = await fundApi.syncStatus()
    lastCheckedAt.value = new Date().toLocaleTimeString('zh-CN')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchStatus()
  timer.value = setInterval(fetchStatus, 60_000)
})

onBeforeUnmount(() => {
  if (timer.value) clearInterval(timer.value)
})

/** 净值滞后天数：只对工作日敏感，这里做粗略提示 */
const navLagDays = computed(() => {
  if (!status.value?.latest_nav_date) return null
  const latest = new Date(status.value.latest_nav_date)
  return Math.max(0, Math.floor((Date.now() - latest.getTime()) / 86_400_000))
})

const freshness = computed(() => {
  if (navLagDays.value === null) return { text: '暂无净值数据', type: 'info' as const }
  if (navLagDays.value <= 1) return { text: '数据新鲜', type: 'success' as const }
  if (navLagDays.value <= 3) return { text: '数据滞后', type: 'warning' as const }
  return { text: '数据严重滞后，请检查采集任务', type: 'danger' as const }
})

const cards = computed(() => [
  { label: '基金总数', value: status.value?.fund_total ?? 0, icon: 'Coin' },
  { label: '净值记录条数', value: status.value?.nav_rows ?? 0, icon: 'DataLine' },
  { label: '最新净值日期', value: status.value?.latest_nav_date ?? '—', icon: 'Calendar' },
])
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">采集监控</h2>
      <div class="header-actions">
        <span class="muted">最近检查 {{ lastCheckedAt || '—' }}（每分钟自动刷新）</span>
        <el-button :loading="loading" @click="fetchStatus">立即刷新</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col v-for="card in cards" :key="card.label" :xs="24" :sm="8">
        <div class="card stat">
          <div class="stat__icon">
            <el-icon :size="22"><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat__body">
            <div class="stat__label">{{ card.label }}</div>
            <div class="stat__value">
              <el-skeleton v-if="loading" :rows="0" animated style="width: 90px" />
              <template v-else>
                {{
                  typeof card.value === 'number' ? card.value.toLocaleString('zh-CN') : card.value
                }}
              </template>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="card">
      <div class="card-head">
        <h3 class="section-title">数据新鲜度</h3>
        <el-tag v-if="!loading" :type="freshness.type" effect="light">{{ freshness.text }}</el-tag>
      </div>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="净值来源">AkShare 公开接口（T+1 更新）</el-descriptions-item>
        <el-descriptions-item label="采集方式">
          定时脚本批量拉取，正演同步任务见 services/api/app/jobs
        </el-descriptions-item>
        <el-descriptions-item label="基金覆盖">
          {{ status ? `${status.fund_total.toLocaleString('zh-CN')} 只（全市场开放式基金）` : '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="净值覆盖">
          {{ status ? `${status.nav_rows.toLocaleString('zh-CN')} 条历史净值` : '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="最新净值日期">
          {{ formatDate(status?.latest_nav_date) }}
        </el-descriptions-item>
        <el-descriptions-item label="滞后天数">
          {{ navLagDays === null ? '—' : `${navLagDays} 天` }}
        </el-descriptions-item>
      </el-descriptions>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="采集任务历史（每次采集的开始/结束/条数/错误）将在 sync_jobs 表上线后在此展示"
        style="margin-top: 16px"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.muted {
  font-size: 13px;
  color: $text-secondary;
}

.header-actions {
  display: flex;
  gap: 14px;
  align-items: center;
}

.stat {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 16px;

  &__icon {
    display: grid;
    flex: none;
    place-items: center;
    width: 44px;
    height: 44px;
    color: $color-primary;
    background: rgb(37 99 235 / 10%);
    border-radius: 10px;
  }

  &__label {
    font-size: 13px;
    color: $text-secondary;
  }

  &__value {
    margin-top: 2px;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.2;
  }
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
</style>
