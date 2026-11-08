<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ARTICLE_CATEGORY_MAP,
  ARTICLE_STATUS_MAP,
  DEFAULT_PAGE_SIZE,
  PAGE_SIZE_OPTIONS,
  formatDateTime,
  type ArticleListItem,
  type ArticleStatus,
} from '@project/shared'

import { articleApi, fundApi } from '@/api'
import { csvFilename, exportCsv } from '@/utils/export'

/** 列表页负责检索、批量操作与导出；新建/编辑跳独立页 */
const router = useRouter()

const loading = ref(false)
const rows = ref<ArticleListItem[]>([])
const total = ref(0)
const selected = ref<ArticleListItem[]>([])
const batchSubmitting = ref(false)
const syncing = ref(false)
const query = reactive({
  page: 1,
  page_size: DEFAULT_PAGE_SIZE,
  keyword: '',
  status: undefined as ArticleStatus | undefined,
})

const statusOptions = Object.entries(ARTICLE_STATUS_MAP).map(([value, item]) => ({
  value: value as ArticleStatus,
  label: item.label,
}))

function categoryLabel(category: string) {
  return ARTICLE_CATEGORY_MAP[category]?.label ?? '其他'
}

/**
 * 一键同步资讯快讯。复用 fundApi 的同步任务通道（mode=news），
 * 轮询到任务结束后再刷新列表，让编辑立刻看到新草稿。
 */
async function handleSyncNews() {
  syncing.value = true
  try {
    const job = await fundApi.triggerSync({ mode: 'news' })
    ElMessage.info('正在抓取政策 / 市场快讯…')
    for (let i = 0; i < 20; i++) {
      await new Promise((resolve) => setTimeout(resolve, 1500))
      const current = await fundApi.syncJob(job.id)
      if (current.status !== 'running') {
        if (current.status === 'success') {
          ElMessage.success(current.message || '同步完成，草稿已生成')
        } else {
          ElMessage.warning('同步未成功，请到「采集监控」查看任务日志')
        }
        await fetchList()
        break
      }
    }
  } finally {
    syncing.value = false
  }
}

function statusMeta(status: ArticleStatus) {
  return ARTICLE_STATUS_MAP[status]
}

async function fetchList() {
  loading.value = true
  try {
    const result = await articleApi.list({
      page: query.page,
      page_size: query.page_size,
      keyword: query.keyword || undefined,
      status: query.status,
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
  query.keyword = ''
  query.status = undefined
  query.page = 1
  fetchList()
}

async function togglePublish(row: ArticleListItem) {
  const next: ArticleStatus = row.status === 'published' ? 'draft' : 'published'
  const action = next === 'published' ? '发布' : '撤回'
  const confirmed = await ElMessageBox.confirm(
    `确定${action}《${row.title}》吗？`,
    `${action}确认`,
    { type: 'warning' },
  ).catch(() => false)
  if (!confirmed) return

  await articleApi.update(row.id, { status: next })
  ElMessage.success(`已${action}`)
  await fetchList()
}

async function handleDelete(row: ArticleListItem) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除《${row.title}》吗？删除后不可恢复。`,
    '删除确认',
    {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    },
  ).catch(() => false)
  if (!confirmed) return

  await articleApi.remove(row.id)
  ElMessage.success('已删除')
  await fetchList()
}

/** ---------- 批量操作 ---------- */

function selectedIds(): number[] {
  return selected.value.map((a) => a.id)
}

async function runBatch(action: () => Promise<{ affected: number }>, label: string) {
  batchSubmitting.value = true
  try {
    const { affected } = await action()
    ElMessage.success(`已${label} ${affected} 篇`)
    selected.value = []
    await fetchList()
  } finally {
    batchSubmitting.value = false
  }
}

async function handleBatchPublish() {
  const ids = selectedIds()
  const confirmed = await ElMessageBox.confirm(
    `确定发布选中的 ${ids.length} 篇文章吗？`,
    '批量发布',
    {
      type: 'warning',
    },
  ).catch(() => false)
  if (!confirmed) return
  await runBatch(() => articleApi.batchStatus(ids, 'published'), '发布')
}

async function handleBatchWithdraw() {
  const ids = selectedIds()
  const confirmed = await ElMessageBox.confirm(
    `确定撤回选中的 ${ids.length} 篇文章吗？`,
    '批量撤回',
    {
      type: 'warning',
    },
  ).catch(() => false)
  if (!confirmed) return
  await runBatch(() => articleApi.batchStatus(ids, 'draft'), '撤回')
}

async function handleBatchDelete() {
  const ids = selectedIds()
  const confirmed = await ElMessageBox.confirm(
    `确定删除选中的 ${ids.length} 篇文章吗？删除后不可恢复。`,
    '批量删除',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) return
  await runBatch(() => articleApi.batchRemove(ids), '删除')
}

function handleExport() {
  exportCsv(csvFilename('articles'), rows.value, [
    { header: 'ID', value: (a) => a.id },
    { header: '标题', value: (a) => a.title },
    { header: 'Slug', value: (a) => a.slug },
    { header: '分类', value: (a) => categoryLabel(a.category) },
    { header: '来源', value: (a) => a.source_name ?? '原创' },
    { header: '状态', value: (a) => ARTICLE_STATUS_MAP[a.status]?.label ?? a.status },
    { header: '浏览量', value: (a) => a.view_count },
    { header: '发布时间', value: (a) => formatDateTime(a.published_at) },
  ])
  ElMessage.success(`已导出当前页 ${rows.value.length} 条`)
}

onMounted(fetchList)
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">文章管理</h2>
      <div class="header-actions">
        <el-button type="info" plain :loading="syncing" @click="handleSyncNews">
          <el-icon><Refresh /></el-icon>同步资讯
        </el-button>
        <el-button :disabled="!rows.length" @click="handleExport">
          <el-icon><Download /></el-icon>导出 CSV
        </el-button>
        <el-button
          type="success"
          plain
          :disabled="!selected.length"
          :loading="batchSubmitting"
          @click="handleBatchPublish"
        >
          批量发布{{ selected.length ? `（${selected.length}）` : '' }}
        </el-button>
        <el-button
          type="warning"
          plain
          :disabled="!selected.length"
          :loading="batchSubmitting"
          @click="handleBatchWithdraw"
        >
          批量撤回
        </el-button>
        <el-button
          type="danger"
          plain
          :disabled="!selected.length"
          :loading="batchSubmitting"
          @click="handleBatchDelete"
        >
          批量删除
        </el-button>
        <el-button type="primary" @click="router.push({ name: 'article-create' })">
          <el-icon><Plus /></el-icon>新建文章
        </el-button>
      </div>
    </div>

    <div class="card">
      <p class="sync-hint">
        同步进来的快讯只含标题、摘要、来源与原文链接，默认是<strong>草稿</strong>，
        审核并补充原创正文后再发布；请勿直接全文转载。
      </p>
      <div class="filter-bar">
        <el-input
          v-model="query.keyword"
          placeholder="标题关键词"
          clearable
          style="width: 220px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-select
          v-model="query.status"
          placeholder="状态"
          clearable
          style="width: 140px"
          @change="handleSearch"
        >
          <el-option
            v-for="item in statusOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-button type="primary" plain @click="handleSearch">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="rows"
        stripe
        border
        @selection-change="(vals: ArticleListItem[]) => (selected = vals)"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
        <el-table-column prop="slug" label="Slug" min-width="160" show-overflow-tooltip />
        <el-table-column label="分类" width="90">
          <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
        </el-table-column>
        <el-table-column label="来源" width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-if="row.origin === 'sync'" size="small" type="info">
              {{ row.source_name || '外部' }}
            </el-tag>
            <span v-else class="muted">原创</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMeta(row.status).type" size="small">
              {{ statusMeta(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="view_count" label="浏览" width="80" />
        <el-table-column label="发布时间" width="160">
          <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              size="small"
              @click="router.push({ name: 'article-edit', params: { id: row.id } })"
              >编辑</el-button
            >
            <el-button
              link
              type="success"
              size="small"
              @click="togglePublish(row as ArticleListItem)"
            >
              {{ row.status === 'published' ? '撤回' : '发布' }}
            </el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row as ArticleListItem)"
              >删除</el-button
            >
          </template>
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
.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.sync-hint {
  margin: 0 0 14px;
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--el-text-color-secondary);

  strong {
    color: var(--el-color-warning);
  }
}

.muted {
  color: var(--el-text-color-placeholder);
}
</style>
