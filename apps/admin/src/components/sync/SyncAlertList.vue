<script setup lang="ts">
import type { SyncAlert } from '@/types/admin'

/** 采集告警：只做展示，处理入口在任务表（取消/重试）。 */
defineProps<{ alerts: SyncAlert[] }>()
</script>

<template>
  <div v-if="alerts.length" class="alerts">
    <el-alert
      v-for="alert in alerts"
      :key="`${alert.job_id}-${alert.title}`"
      :type="alert.level === 'error' ? 'error' : 'warning'"
      :title="alert.title"
      :description="alert.detail"
      :closable="false"
      show-icon
      class="alerts__item"
    />
  </div>
</template>

<style scoped lang="scss">
.alerts {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.alerts__item {
  :deep(.el-alert__description) {
    margin-top: 2px;
    font-size: 12.5px;
  }
}
</style>
