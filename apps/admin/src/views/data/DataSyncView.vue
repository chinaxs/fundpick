<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { formatDate, formatDateTime } from '@project/shared'

import { fundApi } from '@/api'
import DataQualityPanel from '@/components/sync/DataQualityPanel.vue'
import SyncAlertList from '@/components/sync/SyncAlertList.vue'
import SyncJobTable from '@/components/sync/SyncJobTable.vue'
import SyncSchedulePanel from '@/components/sync/SyncSchedulePanel.vue'
import { useAuthStore } from '@/stores/auth'
import {
  SYNC_MODE_OPTIONS,
  type SyncAlert,
  type SyncJob,
  type SyncStatus,
  type SyncTriggerPayload,
} from '@/types/admin'

const authStore = useAuthStore()

/** 采集监控：概况 + 手动触发 + 任务中心 + 定时 + 数据质量 */
const status = ref<SyncStatus | null>(null)
const jobs = ref<SyncJob[]>([])
const alerts = ref<SyncAlert[]>([])
const loading = ref(true)
const lastCheckedAt = ref('')
const qualityRef = ref<InstanceType<typeof DataQualityPanel>>()
const timer = ref<ReturnType<typeof setInterval>>()
const pollTimer = ref<ReturnType<typeof setInterval>>()

// 触发表单
const syncMode = ref('quick')
const syncLimit = ref<number | null>(null)
const syncCodes = ref('')
const triggering = ref(false)
const logVisible = ref(false)
const currentLog = ref('')

const modeHint = computed(
  () => SYNC_MODE_OPTIONS.find((option) => option.value === syncMode.value)?.hint ?? '',
)
const runningJob = computed(
  () => jobs.value.find((job) => job.status === 'starting' || job.status === 'running') ?? null,
)

async function fetchStatus(silent = false) {
  try {
    status.value = await fundApi.syncStatus()
    lastCheckedAt.value = new Date().toLocaleTimeString('zh-CN')
  } catch (error) {
    if (!silent) ElMessage.error(error instanceof Error ? error.message : '刷新数据状态失败')
  } finally {
    loading.value = false
  }
}

async function fetchAlerts(silent = true) {
  try {
    alerts.value = await fundApi.syncAlerts(24)
  } catch (error) {
    if (!silent) ElMessage.error(error instanceof Error ? error.message : '加载告警失败')
  }
}

async function fetchJobs(silent = false) {
  const hadRunningJob = Boolean(runningJob.value)
  try {
    jobs.value = await fundApi.syncJobs(20)
  } catch (error) {
    if (!silent) ElMessage.error(error instanceof Error ? error.message : '刷新任务状态失败')
    return
  }
  if (runningJob.value) {
    startPolling()
  } else if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = undefined
  }
  if (hadRunningJob && !runningJob.value) {
    void fetchAlerts(false)
    void qualityRef.value?.refresh()
    void fetchStatus(true)
  }
}

async function refreshAll() {
  await Promise.all([fetchStatus(), fetchJobs(), fetchAlerts(false)])
}

function startPolling() {
  if (pollTimer.value) return
  pollTimer.value = setInterval(() => void fetchJobs(true), 3000)
}

async function triggerSync() {
  const option = SYNC_MODE_OPTIONS.find((item) => item.value === syncMode.value)
  try {
    await ElMessageBox.confirm(
      `确认执行一次「${option?.label ?? syncMode.value}」同步？\n${modeHint.value}\n采集在后台子进程运行，期间可继续使用后台。`,
      '立即同步',
      { confirmButtonText: '开始同步', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  const payload: SyncTriggerPayload = { mode: syncMode.value }
  if (syncLimit.value && syncLimit.value > 0) payload.limit = syncLimit.value
  if (syncCodes.value.trim()) payload.codes = syncCodes.value.trim()
  if (syncMode.value === 'sector') payload.force = true

  triggering.value = true
  try {
    const job = await fundApi.triggerSync(payload)
    if (job.status === 'failed') {
      ElMessage.error(job.message || `同步任务 #${job.id} 启动失败`)
    } else {
      ElMessage.success(`同步任务 #${job.id} 已启动，可在下方查看进度`)
    }
    await fetchJobs()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '启动失败')
  } finally {
    triggering.value = false
  }
}

async function cancelJob(job: SyncJob) {
  try {
    await ElMessageBox.confirm(
      `取消任务 #${job.id}（${job.mode}）？脚本会在处理完当前条目后停止，已写入的数据保留。`,
      '取消任务',
      { confirmButtonText: '取消任务', cancelButtonText: '继续运行', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await fundApi.cancelSync(job.id)
    ElMessage.success('已请求取消')
    await fetchJobs()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '取消失败')
  }
}

async function retryJob(job: SyncJob) {
  try {
    await ElMessageBox.confirm(`用任务 #${job.id} 的模式与参数重跑一次？`, '重试任务', {
      confirmButtonText: '重试',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    const created = await fundApi.retrySync(job.id)
    ElMessage.success(`已创建任务 #${created.id}`)
    await fetchJobs()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '重试失败')
  }
}

function showLog(job: SyncJob) {
  currentLog.value = job.log_tail || job.message || '暂无日志'
  logVisible.value = true
}

onMounted(() => {
  startPolling()
  void refreshAll()
  timer.value = setInterval(() => void fetchStatus(true), 60_000)
})

onBeforeUnmount(() => {
  if (timer.value) clearInterval(timer.value)
  if (pollTimer.value) clearInterval(pollTimer.value)
})

/** The API owns the Beijing calendar and publication deadline. */
const freshness = computed(() => {
  if (!status.value) return { text: '正在核对', type: 'info' as const }
  const current = status.value.freshness_state === 'current'
  if (current && ((status.value.lagging_funds ?? 0) > 0 || status.value.missing_nav_funds > 0))
    return { text: '部分基金仍需补采', type: 'warning' as const }
  return {
    text: current
      ? '最新披露已覆盖基准'
      : status.value.freshness_state === 'lagging'
        ? '未达到披露基准'
        : '数据待核对',
    type: current ? ('success' as const) : ('warning' as const),
  }
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
        <el-button :loading="loading" @click="refreshAll">立即刷新</el-button>
      </div>
    </div>

    <SyncAlertList :alerts="alerts" />

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

    <!-- 手动触发同步 -->
    <div class="card">
      <div class="card-head">
        <h3 class="section-title">立即同步</h3>
        <el-tag v-if="runningJob" type="primary" effect="light">
          任务 #{{ runningJob.id }} 运行中…
        </el-tag>
      </div>

      <div class="sync-form">
        <el-select v-model="syncMode" style="width: 230px" :disabled="!!runningJob">
          <el-option
            v-for="option in SYNC_MODE_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-input-number
          v-model="syncLimit"
          :min="1"
          :max="50000"
          :step="100"
          placeholder="数量上限（可选）"
          controls-position="right"
          style="width: 180px"
          :disabled="!!runningJob"
        />
        <el-input
          v-model="syncCodes"
          placeholder="指定基金代码，逗号分隔（可选）"
          clearable
          style="width: 260px"
          :disabled="!!runningJob"
        />
        <el-button
          v-if="authStore.isSuperuser"
          type="primary"
          :loading="triggering"
          :disabled="!!runningJob"
          @click="triggerSync"
        >
          {{ runningJob ? '同步进行中' : '立即同步' }}
        </el-button>
        <el-tooltip v-else content="仅超级管理员可触发同步" placement="top">
          <el-button type="primary" disabled>立即同步</el-button>
        </el-tooltip>
      </div>

      <p class="sync-hint">
        {{ modeHint }}。采集脚本在独立子进程执行，接口立即返回；超管操作会记入审计日志。
        同一时间只允许一个同步任务，可随时取消。
      </p>
    </div>

    <div class="card">
      <div class="card-head">
        <h3 class="section-title">数据新鲜度</h3>
        <el-tag v-if="!loading" :type="freshness.type" effect="light">{{ freshness.text }}</el-tag>
      </div>

      <el-alert
        v-if="status && (!status.scheduler_enabled || !status.enabled_schedules)"
        title="尚未启用自动同步计划，请在下方补齐推荐计划。"
        type="warning"
        :closable="false"
      />
      <p class="sync-hint">
        {{
          status?.freshness_message
        }}。22:00为境内普通基金的运营核对时间，非所有品种的保证发布时间。
      </p>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="净值来源"
          >公开基金净值；按交易日和披露时间核对</el-descriptions-item
        >
        <el-descriptions-item label="采集方式">
          手动触发 / 定时调度；另支持命令行 CLI 与详情页按需回填
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
        <el-descriptions-item label="应披露基准">{{
          status?.expected_nav_date ?? '交易日历未知'
        }}</el-descriptions-item>
        <el-descriptions-item label="缺失交易日"
          >{{ status?.nav_lag_trading_days ?? '—' }}（周末、节假日不计）</el-descriptions-item
        >
        <el-descriptions-item label="普通基金覆盖"
          >已达基准 {{ status?.current_funds ?? '—' }} · 待更新 {{ status?.lagging_funds ?? '—' }} ·
          无净值 {{ status?.missing_nav_funds ?? '—' }}</el-descriptions-item
        >
        <el-descriptions-item label="特殊品种"
          >{{
            status?.special_funds ?? '—'
          }}
          只，QDII/FOF或暂停品种按各自披露规则核对</el-descriptions-item
        >
        <el-descriptions-item label="定时同步"
          >{{ status?.scheduler_enabled ? '调度器已开启' : '调度器未开启' }} ·
          {{ status?.enabled_schedules ?? 0 }} 条启用计划</el-descriptions-item
        >
        <el-descriptions-item label="最近数据同步">{{
          formatDateTime(status?.last_data_sync_at)
        }}</el-descriptions-item>
        <el-descriptions-item label="自动入账"
          >{{
            status?.auto_reconcile_enabled
              ? `后台每${status.auto_reconcile_interval_seconds}秒检查`
              : '未开启'
          }}
          · {{ status?.pending_automatic ?? 0 }} 笔待处理</el-descriptions-item
        >
        <el-descriptions-item label="最近入账核对">{{
          formatDateTime(status?.last_automatic_check_at)
        }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="card">
      <div class="card-head">
        <h3 class="section-title">同步任务</h3>
      </div>
      <SyncJobTable
        :jobs="jobs"
        :modes="SYNC_MODE_OPTIONS"
        :can-operate="authStore.isSuperuser"
        @refresh="fetchJobs()"
        @cancel="cancelJob"
        @retry="retryJob"
        @view-log="showLog"
      />
    </div>

    <SyncSchedulePanel :can-edit="authStore.isSuperuser" />

    <DataQualityPanel
      ref="qualityRef"
      :blocked="!!runningJob || triggering"
      @job-started="fetchJobs()"
    />

    <el-dialog v-model="logVisible" title="同步日志（末尾摘录）" width="720px">
      <pre class="log-box">{{ currentLog }}</pre>
    </el-dialog>
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

.sync-form {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.sync-hint {
  margin: 12px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: $text-secondary;
}

@media (max-width: 640px) {
  .card-head {
    flex-wrap: wrap;
    gap: 12px;
  }
}

.log-box {
  max-height: 420px;
  padding: 14px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}
</style>
