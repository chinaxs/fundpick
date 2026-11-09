<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { formatDateTime } from '@project/shared'

import { systemApi } from '@/api'
import type { OpsStatus } from '@/types/admin'

/** 运行健康度：日志是否留存、备份是否可用、当前有没有要处理的事。 */
const data = ref<OpsStatus | null>(null)
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    data.value = await systemApi.health()
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
}

function size(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const CATEGORY_LABELS: Record<string, string> = {
  data: '数据',
  sync: '采集',
  backup: '备份',
  logs: '日志',
}

function categoryLabel(category: string) {
  return CATEGORY_LABELS[category] ?? category
}

onMounted(() => void load())
</script>

<template>
  <div class="card">
    <div class="card-head">
      <h3 class="section-title">运行健康度</h3>
      <el-button size="small" :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-skeleton v-if="loading" :rows="4" animated />

    <template v-else-if="data">
      <el-alert
        v-if="data.alerts.length"
        type="warning"
        :closable="false"
        show-icon
        :title="`${data.alerts.length} 项需要关注`"
        class="summary"
      />
      <el-alert
        v-else
        type="success"
        :closable="false"
        show-icon
        title="数据、采集、备份与日志均正常"
        class="summary"
      />

      <div v-if="data.alerts.length" class="alerts">
        <div v-for="alert in data.alerts" :key="alert.title" class="alert">
          <el-tag
            :type="alert.level === 'error' ? 'danger' : 'warning'"
            size="small"
            effect="light"
          >
            {{ categoryLabel(alert.category) }}
          </el-tag>
          <div>
            <div class="alert__title">{{ alert.title }}</div>
            <div class="alert__detail">{{ alert.detail }}</div>
          </div>
        </div>
      </div>

      <el-row :gutter="16" class="blocks">
        <el-col :xs="24" :md="12">
          <h4 class="block-title">数据库备份</h4>
          <div v-if="data.backup" class="block">
            <div class="row">
              <span>最新备份</span><span>{{ data.backup.name }}</span>
            </div>
            <div class="row">
              <span>生成时间</span><span>{{ formatDateTime(data.backup.created_at) }}</span>
            </div>
            <div class="row">
              <span>大小 / 份数</span>
              <span>{{ size(data.backup.size_bytes) }} · {{ data.backup.total_backups }} 份</span>
            </div>
            <div class="row">
              <span>最近恢复演练</span>
              <span>
                {{ formatDateTime(data.backup.restore_drill_at) }}
                <el-tag
                  v-if="data.backup.restore_drill_ok === true"
                  type="success"
                  size="small"
                  effect="light"
                  >通过</el-tag
                >
                <el-tag
                  v-else-if="data.backup.restore_drill_ok === false"
                  type="danger"
                  size="small"
                  effect="light"
                  >失败</el-tag
                >
              </span>
            </div>
            <p class="command">
              定时任务建议：<code>python -m scripts.backup_db</code> 每日一次，
              <code>python -m scripts.restore_drill</code> 每周一次
            </p>
          </div>
          <p v-else class="muted">
            还没有备份。运行 <code>python -m scripts.backup_db</code> 生成第一份。
          </p>
        </el-col>

        <el-col :xs="24" :md="12">
          <h4 class="block-title">日志文件</h4>
          <el-table :data="data.logs" size="small" border empty-text="没有找到日志文件">
            <el-table-column prop="name" label="文件" min-width="180" show-overflow-tooltip />
            <el-table-column label="大小" width="100">
              <template #default="{ row }">{{ size(row.size_bytes) }}</template>
            </el-table-column>
            <el-table-column label="更新时间" width="170">
              <template #default="{ row }">{{ formatDateTime(row.modified_at) }}</template>
            </el-table-column>
          </el-table>
          <p class="muted">
            容器部署时请把 <code>services/api/logs</code> 挂到持久卷，否则重建即丢。
          </p>
        </el-col>
      </el-row>

      <p class="checked">检查时间 {{ formatDateTime(data.checked_at) }}</p>
    </template>

    <p v-else class="muted">暂时取不到运行状态，请检查后端服务。</p>
  </div>
</template>

<style scoped lang="scss">
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.summary {
  margin-bottom: 12px;
}

.alerts {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.alert {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px 12px;
  background: #fffbeb;
  border-radius: $radius-base;

  &__title {
    font-size: 13.5px;
    font-weight: 600;
  }

  &__detail {
    font-size: 12.5px;
    line-height: 1.6;
    color: $text-secondary;
  }
}

.blocks {
  margin-top: 4px;
}

.block-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
}

.block {
  padding: 12px;
  background: $bg-page;
  border-radius: $radius-base;
}

.row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12.5px;

  span:first-child {
    color: $text-secondary;
  }
}

.command {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: $text-secondary;
}

code {
  padding: 1px 5px;
  font-size: 11.5px;
  background: #eef2f7;
  border-radius: 4px;
}

.muted {
  margin: 8px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: $text-secondary;
}

.checked {
  margin: 12px 0 0;
  font-size: 12px;
  color: $text-secondary;
}
</style>
