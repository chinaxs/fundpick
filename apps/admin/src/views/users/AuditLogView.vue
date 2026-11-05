<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, formatDateTime, fromNow } from '@project/shared'

import { auditApi } from '@/api'
import type { AuditLogItem } from '@/types/admin'

/** 操作审计：后台所有写操作（POST/PATCH/DELETE）由中间件自动落库 */
const loading = ref(false)
const rows = ref<AuditLogItem[]>([])
const total = ref(0)

const query = reactive({
  username: '',
  resource: '',
  status_code: undefined as number | undefined,
  range: null as [string, string] | null,
  page: 1,
  page_size: DEFAULT_PAGE_SIZE,
})

/** 供下拉选择的资源类型（与后端 resource 字段对应） */
const resourceOptions = [
  { value: 'users', label: '用户' },
  { value: 'articles', label: '文章' },
  { value: 'funds', label: '基金' },
  { value: 'auth', label: '认证' },
]

const statusOptions = [
  { value: 200, label: '200 成功' },
  { value: 400, label: '400 参数错误' },
  { value: 401, label: '401 未授权' },
  { value: 403, label: '403 无权限' },
  { value: 404, label: '404 不存在' },
  { value: 500, label: '500 服务错误' },
]

async function fetchList() {
  loading.value = true
  try {
    const result = await auditApi.list({
      username: query.username || undefined,
      resource: query.resource || undefined,
      status_code: query.status_code,
      start: query.range?.[0],
      end: query.range?.[1],
      page: query.page,
      page_size: query.page_size,
    })
    rows.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  fetchList()
}

function resetQuery() {
  query.username = ''
  query.resource = ''
  query.status_code = undefined
  query.range = null
  query.page = 1
  fetchList()
}

function actionTag(method: string): {
  label: string
  type: 'success' | 'warning' | 'danger' | 'info'
} {
  if (method === 'POST') return { label: '新增', type: 'success' }
  if (method === 'PUT' || method === 'PATCH') return { label: '修改', type: 'warning' }
  if (method === 'DELETE') return { label: '删除', type: 'danger' }
  return { label: method, type: 'info' }
}

onMounted(fetchList)
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">操作日志</h2>
      <span class="muted">后台写操作（新增 / 修改 / 删除）自动记录，不可篡改</span>
    </div>

    <div class="card">
      <div class="filter-bar">
        <el-input
          v-model="query.username"
          placeholder="操作人用户名"
          clearable
          style="width: 160px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-select
          v-model="query.resource"
          placeholder="资源类型"
          clearable
          style="width: 140px"
          @change="handleSearch"
        >
          <el-option v-for="item in resourceOptions" :key="item.value" v-bind="item" />
        </el-select>
        <el-select
          v-model="query.status_code"
          placeholder="状态码"
          clearable
          style="width: 150px"
          @change="handleSearch"
        >
          <el-option
            v-for="item in statusOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-date-picker
          v-model="query.range"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          style="width: 360px"
          value-format="YYYY-MM-DDTHH:mm:ss"
          @change="handleSearch"
        />
        <el-button type="primary" plain @click="handleSearch">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="rows" stripe border>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="操作人" width="110">
          <template #default="{ row }">{{ row.username ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-tag :type="actionTag(row.method).type" size="small">
              {{ actionTag(row.method).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="method" label="Method" width="90">
          <template #default="{ row }">
            <code class="method">{{ row.method }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="接口路径" min-width="260" show-overflow-tooltip />
        <el-table-column prop="resource" label="资源" width="110" show-overflow-tooltip />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <span :class="row.status_code < 400 ? 'ok' : 'fail'">{{ row.status_code }}</span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90">
          <template #default="{ row }">{{
            row.duration_ms != null ? `${row.duration_ms}ms` : '—'
          }}</template>
        </el-table-column>
        <el-table-column label="IP" width="120">
          <template #default="{ row }">{{ row.ip ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="时间" width="160">
          <template #default="{ row }">
            <el-tooltip :content="formatDateTime(row.created_at)" placement="top">
              <span>{{ fromNow(row.created_at) }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.detail ?? '—' }}</template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[...PAGE_SIZE_OPTIONS]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="fetchList"
        />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.muted {
  font-size: 13px;
  color: $text-secondary;
}

.method {
  padding: 1px 6px;
  font-family: 'SFMono-Regular', Consolas, Menlo, monospace;
  font-size: 12px;
  background: $bg-page;
  border-radius: 4px;
}

.ok {
  color: #16a34a;
}

.fail {
  color: #ef4444;
}
</style>
