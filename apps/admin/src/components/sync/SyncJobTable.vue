<script setup lang="ts">
import { formatDateTime } from '@project/shared'

import type { SyncJob } from '@/types/admin'

/** 任务历史的展示与操作：进度、失败明细、取消、重试、日志。 */
const props = defineProps<{
  jobs: SyncJob[]
  modes: { value: string; label: string }[]
  canOperate: boolean
}>()

const emit = defineEmits<{
  refresh: []
  cancel: [job: SyncJob]
  retry: [job: SyncJob]
  viewLog: [job: SyncJob]
}>()

const activeStatuses = ['starting', 'running']

const statusMap: Record<
  string,
  { type: 'primary' | 'success' | 'warning' | 'danger' | 'info'; text: string }
> = {
  starting: { type: 'warning', text: '启动中' },
  running: { type: 'primary', text: '运行中' },
  partial_success: { type: 'warning', text: '部分成功' },
  success: { type: 'success', text: '成功' },
  failed: { type: 'danger', text: '失败' },
  cancelled: { type: 'info', text: '已取消' },
  timeout: { type: 'danger', text: '超时' },
}

function statusOf(status: string) {
  return statusMap[status] ?? { type: 'info' as const, text: status }
}

function isActive(job: SyncJob) {
  return activeStatuses.includes(job.status)
}

/** 已处理数 = 成功 + 失败 + 跳过；有目标数时换算百分比 */
function percent(job: SyncJob) {
  if (!job.total) return 0
  const handled = job.succeeded + job.failed + job.skipped
  return Math.min(100, Math.round((handled / job.total) * 100))
}

function processed(job: SyncJob) {
  return job.succeeded + job.failed + job.skipped
}

function durationText(ms: number | null) {
  if (ms === null) return '—'
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

function modeLabel(mode: string) {
  return props.modes.find((option) => option.value === mode)?.label ?? mode
}

function hasDetail(job: SyncJob) {
  return job.failures.length > 0 || Boolean(job.log_tail)
}
</script>

<template>
  <el-table :data="jobs" size="small" border empty-text="暂无同步任务">
    <el-table-column type="expand" width="36">
      <template #default="{ row }">
        <div class="detail">
          <div v-if="row.failures.length" class="detail__failures">
            <div class="detail__title">
              失败明细（{{ row.failed }} 条，展示前 {{ row.failures.length }} 条）
            </div>
            <ul>
              <li v-for="failure in row.failures" :key="failure.item">
                <code>{{ failure.item }}</code>
                <span>{{ failure.reason }}</span>
              </li>
            </ul>
          </div>
          <div v-if="row.log_tail" class="detail__log">
            <div class="detail__title">日志末尾</div>
            <pre>{{ row.log_tail }}</pre>
          </div>
          <el-empty
            v-if="!hasDetail(row as SyncJob)"
            description="该任务没有失败明细与日志摘录"
            :image-size="48"
          />
          <div class="detail__meta">
            超时上限 {{ row.timeout_seconds }} 秒 · 心跳 {{ formatDateTime(row.heartbeat_at) }} ·
            PID
            {{ row.pid ?? '—' }}
          </div>
        </div>
      </template>
    </el-table-column>
    <el-table-column prop="id" label="#" width="70" />
    <el-table-column label="模式" min-width="170">
      <template #default="{ row }">{{ modeLabel(row.mode) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="statusOf(row.status).type" effect="light" size="small">
          {{ statusOf(row.status).text }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="阶段 / 进度" min-width="210">
      <template #default="{ row }">
        <div class="progress">
          <div class="progress__head">
            <span class="progress__phase">{{ modeLabel(row.phase || row.mode) }}</span>
            <span class="progress__count">
              {{ processed(row as SyncJob)
              }}<template v-if="row.total"> / {{ row.total }}</template>
            </span>
          </div>
          <el-progress
            :percentage="percent(row as SyncJob)"
            :status="row.status === 'failed' || row.status === 'timeout' ? 'exception' : undefined"
            :stroke-width="6"
            :show-text="false"
            :striped="isActive(row as SyncJob)"
            :striped-flow="isActive(row as SyncJob)"
          />
          <div class="progress__sub">
            成功 {{ row.succeeded }} · 失败 {{ row.failed }} · 跳过 {{ row.skipped }}
          </div>
        </div>
      </template>
    </el-table-column>
    <el-table-column prop="triggered_by" label="触发人" width="110" />
    <el-table-column label="开始时间" width="165">
      <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
    </el-table-column>
    <el-table-column label="耗时" width="95">
      <template #default="{ row }">{{ durationText(row.duration_ms) }}</template>
    </el-table-column>
    <el-table-column label="结果" min-width="180" show-overflow-tooltip>
      <template #default="{ row }">{{ row.message || '—' }}</template>
    </el-table-column>
    <el-table-column label="操作" width="170" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" size="small" @click="emit('viewLog', row as SyncJob)">
          日志
        </el-button>
        <el-button
          v-if="isActive(row as SyncJob)"
          link
          type="danger"
          size="small"
          :disabled="!canOperate || row.cancel_requested"
          @click="emit('cancel', row as SyncJob)"
        >
          {{ row.cancel_requested ? '取消中' : '取消' }}
        </el-button>
        <el-button
          v-else
          link
          type="primary"
          size="small"
          :disabled="!canOperate"
          @click="emit('retry', row as SyncJob)"
        >
          重试
        </el-button>
      </template>
    </el-table-column>
  </el-table>

  <div class="footer">
    <span class="footer__hint">阶段与计数由采集脚本写进度文件回填，约 1 秒刷新一次。</span>
    <el-button size="small" @click="emit('refresh')">刷新</el-button>
  </div>
</template>

<style scoped lang="scss">
.progress {
  display: flex;
  flex-direction: column;
  gap: 3px;

  &__head {
    display: flex;
    justify-content: space-between;
    font-size: 12.5px;
  }

  &__phase {
    color: $text-primary;
  }

  &__count {
    color: $text-secondary;
  }

  &__sub {
    font-size: 11.5px;
    color: $text-secondary;
  }
}

.detail {
  padding: 8px 16px 12px 48px;
  font-size: 12.5px;

  &__title {
    margin-bottom: 6px;
    font-weight: 600;
  }

  &__failures ul {
    padding-left: 18px;
    margin: 0 0 10px;

    li {
      margin-bottom: 4px;
    }

    code {
      padding: 0 4px;
      margin-right: 8px;
      background: #f1f5f9;
      border-radius: 4px;
    }
  }

  &__log pre {
    max-height: 220px;
    padding: 10px;
    overflow: auto;
    font-size: 11.5px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-all;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
  }

  &__meta {
    margin-top: 8px;
    color: $text-secondary;
  }
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;

  &__hint {
    font-size: 12px;
    color: $text-secondary;
  }
}
</style>
