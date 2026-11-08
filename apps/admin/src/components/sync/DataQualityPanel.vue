<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { formatDate } from '@project/shared'

import { fundApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { SYNC_MODE_OPTIONS, type DataQualityIssue, type DataQualityReport } from '@/types/admin'

/** 数据质量：汇总、问题清单与定向补采入口。 */
const props = defineProps<{ blocked: boolean }>()
const emit = defineEmits<{ jobStarted: [] }>()

const authStore = useAuthStore()
const report = ref<DataQualityReport | null>(null)
const loading = ref(true)
const page = ref(1)
const keyword = ref('')
const triggering = ref(false)

async function fetchReport(silent = false) {
  loading.value = true
  try {
    report.value = await fundApi.dataQuality({
      page: page.value,
      page_size: 50,
      ...(keyword.value.trim() ? { keyword: keyword.value.trim() } : {}),
    })
  } catch (error) {
    if (!silent) ElMessage.error(error instanceof Error ? error.message : '检查数据质量失败')
  } finally {
    loading.value = false
  }
}

async function search() {
  page.value = 1
  await fetchReport()
}

async function loadPage(next: number) {
  page.value = next
  await fetchReport()
}

function modeLabel(mode: string) {
  return SYNC_MODE_OPTIONS.find((option) => option.value === mode)?.label ?? mode
}

async function triggerTargetedSync(issue: DataQualityIssue) {
  if (props.blocked || triggering.value) return
  try {
    await ElMessageBox.confirm(
      `为 ${issue.code} ${issue.name} 执行「${modeLabel(issue.suggested_mode)}」定向补采？`,
      '定向补采',
      { confirmButtonText: '开始补采', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  triggering.value = true
  try {
    const job = await fundApi.triggerSync({ mode: issue.suggested_mode, codes: issue.code })
    if (job.status === 'failed') ElMessage.error(job.message || `任务 #${job.id} 启动失败`)
    else ElMessage.success(`基金 ${issue.code} 的补采任务 #${job.id} 已提交`)
    emit('jobStarted')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '启动补采失败')
  } finally {
    triggering.value = false
  }
}

onMounted(() => void fetchReport(true))

defineExpose({ refresh: () => fetchReport(true) })
</script>

<template>
  <div class="card">
    <div class="card-head">
      <div>
        <h3 class="section-title">数据质量</h3>
        <p v-if="report" class="hint">
          检查日期 {{ report.checked_on }}；净值自然日龄超过
          {{ report.nav_stale_after_days }} 天视为滞后。
        </p>
      </div>
      <div class="actions">
        <el-input
          v-model="keyword"
          clearable
          placeholder="基金名称或代码"
          style="width: 200px"
          @keyup.enter="search"
        />
        <el-button :loading="loading" @click="search">查询</el-button>
        <el-button :loading="loading" @click="fetchReport()">重新检查</el-button>
      </div>
    </div>

    <el-descriptions v-if="report" :column="3" border class="summary">
      <el-descriptions-item label="需处理基金">
        {{ report.summary.affected_funds }} / {{ report.summary.total_funds }}
      </el-descriptions-item>
      <el-descriptions-item label="缺净值">{{ report.summary.missing_nav }}</el-descriptions-item>
      <el-descriptions-item label="净值滞后">{{ report.summary.lagging_nav }}</el-descriptions-item>
      <el-descriptions-item label="缺收益指标">
        {{ report.summary.missing_return }}
      </el-descriptions-item>
      <el-descriptions-item label="风险待刷新">{{
        report.summary.stale_risk
      }}</el-descriptions-item>
      <el-descriptions-item label="档案缺项">{{
        report.summary.missing_profile
      }}</el-descriptions-item>
    </el-descriptions>

    <el-table
      v-if="report"
      v-loading="loading"
      :data="report.items"
      size="small"
      border
      class="table"
      empty-text="未发现待处理的基金数据质量问题"
    >
      <el-table-column prop="code" label="代码" width="100" />
      <el-table-column prop="name" label="基金" min-width="170" show-overflow-tooltip />
      <el-table-column label="检查项" min-width="250" show-overflow-tooltip>
        <template #default="{ row }">{{ row.fields.join('；') }}</template>
      </el-table-column>
      <el-table-column label="最新净值" width="125">
        <template #default="{ row }">{{ formatDate(row.latest_nav_date) }}</template>
      </el-table-column>
      <el-table-column label="风险基准" width="125">
        <template #default="{ row }">{{ formatDate(row.risk_nav_date) }}</template>
      </el-table-column>
      <el-table-column label="建议补采" width="160">
        <template #default="{ row }">{{ modeLabel(row.suggested_mode) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="authStore.isSuperuser"
            link
            type="primary"
            :disabled="blocked || triggering"
            @click="triggerTargetedSync(row as DataQualityIssue)"
          >
            定向补采
          </el-button>
          <el-tooltip v-else content="仅超级管理员可触发同步">
            <el-button link type="primary" disabled>定向补采</el-button>
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="report && report.total > report.page_size"
      :current-page="report.page"
      :page-size="report.page_size"
      :total="report.total"
      layout="total, prev, pager, next"
      class="pagination"
      @current-change="loadPage"
    />
  </div>
</template>

<style scoped lang="scss">
.card-head {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
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
  color: $text-secondary;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.summary {
  margin-bottom: 16px;
}

.pagination {
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
