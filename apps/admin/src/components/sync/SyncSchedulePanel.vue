<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { formatDate } from '@project/shared'

import { fundApi } from '@/api'
import { SYNC_MODE_OPTIONS, type SyncSchedule } from '@/types/admin'

/** 定时采集：每条配置表达"每周几的几点跑哪个模式"。 */
defineProps<{ canEdit: boolean }>()

const weekdayOptions = [
  { value: '1', label: '一' },
  { value: '2', label: '二' },
  { value: '3', label: '三' },
  { value: '4', label: '四' },
  { value: '5', label: '五' },
  { value: '6', label: '六' },
  { value: '7', label: '日' },
]

const schedules = ref<SyncSchedule[]>([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const form = reactive({
  mode: 'quick',
  hour: 18,
  minute: 0,
  weekdays: ['1', '2', '3', '4', '5'],
})

/** el-time-select 只认 "HH:mm"，与 hour/minute 双向同步，避免再存一份时间状态。 */
const timeText = computed({
  get: () => `${String(form.hour).padStart(2, '0')}:${String(form.minute).padStart(2, '0')}`,
  set: (value: string) => {
    const [hour, minute] = value.split(':').map((part) => Number(part) || 0)
    form.hour = hour ?? 0
    form.minute = minute ?? 0
  },
})

async function fetchSchedules(silent = false) {
  loading.value = true
  try {
    schedules.value = await fundApi.syncSchedules()
  } catch (error) {
    if (!silent) ElMessage.error(error instanceof Error ? error.message : '加载定时配置失败')
  } finally {
    loading.value = false
  }
}

async function installRecommended() {
  saving.value = true
  try {
    schedules.value = await fundApi.installRecommendedSchedules()
    ElMessage.success('已补齐推荐计划：早晨补采、晚间三轮更新，按北京时间执行')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '配置失败')
  } finally {
    saving.value = false
  }
}

function openCreate() {
  form.mode = 'quick'
  form.hour = 18
  form.minute = 0
  form.weekdays = ['1', '2', '3', '4', '5']
  dialogVisible.value = true
}

async function submit() {
  saving.value = true
  try {
    await fundApi.createSchedule({
      mode: form.mode,
      hour: form.hour,
      minute: form.minute,
      weekdays: form.weekdays.join(','),
      enabled: true,
    })
    ElMessage.success('已添加定时任务')
    dialogVisible.value = false
    await fetchSchedules()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '添加失败')
  } finally {
    saving.value = false
  }
}

async function toggle(row: SyncSchedule) {
  try {
    await fundApi.updateSchedule(row.id, { enabled: !row.enabled })
    await fetchSchedules(true)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '调整失败')
  }
}

async function remove(row: SyncSchedule) {
  try {
    await ElMessageBox.confirm(
      `删除「${modeLabel(row.mode)} · 每周${weekdayText(row.weekdays)} ${pad(row.hour)}:${pad(row.minute)}」？`,
      '删除定时任务',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await fundApi.removeSchedule(row.id)
    ElMessage.success('已删除')
    await fetchSchedules()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '删除失败')
  }
}

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function modeLabel(mode: string) {
  return SYNC_MODE_OPTIONS.find((option) => option.value === mode)?.label ?? mode
}

function weekdayText(weekdays: string) {
  if (!weekdays) return '每天'
  return weekdays
    .split(',')
    .map((day) => weekdayOptions.find((option) => option.value === day)?.label ?? day)
    .join('、')
}

onMounted(() => void fetchSchedules(true))
</script>

<template>
  <div class="card">
    <div class="card-head">
      <div>
        <h3 class="section-title">定时采集</h3>
        <p class="hint">
          按北京时间执行，证券休市日不采集基金数据；同一时间只运行一个任务，冲突时6小时内补跑。后台自动入账独立每分钟检查。
        </p>
      </div>
      <div v-if="canEdit">
        <el-button size="small" :loading="saving" @click="installRecommended"
          >补齐推荐计划</el-button
        ><el-button type="primary" size="small" @click="openCreate">新增定时</el-button>
      </div>
    </div>

    <el-alert
      v-if="!loading && !schedules.some((row) => row.enabled)"
      title="没有启用的定时计划；手动同步不会自动变成周期更新。"
      type="warning"
      :closable="false"
    />
    <el-table
      v-loading="loading"
      :data="schedules"
      size="small"
      border
      empty-text="尚未配置定时任务，可先用上方「立即同步」手动采集"
    >
      <el-table-column label="模式" min-width="180">
        <template #default="{ row }">{{ modeLabel(row.mode) }}</template>
      </el-table-column>
      <el-table-column label="时间" width="150">
        <template #default="{ row }"
          >每周{{ weekdayText(row.weekdays) }} {{ pad(row.hour) }}:{{ pad(row.minute) }}</template
        >
      </el-table-column>
      <el-table-column label="启用" width="90">
        <template #default="{ row }">
          <el-switch
            :model-value="row.enabled"
            :disabled="!canEdit"
            @change="toggle(row as SyncSchedule)"
          />
        </template>
      </el-table-column>
      <el-table-column label="最近触发" width="170">
        <template #default="{ row }">
          {{ row.last_run_on ? formatDate(row.last_run_on) : '尚未触发' }}
          <span v-if="row.last_job_id" class="muted">#{{ row.last_job_id }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button
            link
            type="danger"
            size="small"
            :disabled="!canEdit"
            @click="remove(row as SyncSchedule)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="新增定时采集" width="460px">
      <el-form label-width="72px">
        <el-form-item label="模式">
          <el-select v-model="form.mode" style="width: 100%">
            <el-option
              v-for="option in SYNC_MODE_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
          <el-time-select
            v-model="timeText"
            start="00:00"
            step="00:15"
            end="23:45"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="星期">
          <el-checkbox-group v-model="form.weekdays">
            <el-checkbox v-for="day in weekdayOptions" :key="day.value" :value="day.value">
              {{ day.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.hint {
  margin: 6px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: $text-secondary;
}

.muted {
  margin-left: 6px;
  font-size: 12px;
  color: $text-secondary;
}
</style>
