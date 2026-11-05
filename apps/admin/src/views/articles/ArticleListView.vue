<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  ARTICLE_STATUS_MAP,
  DEFAULT_PAGE_SIZE,
  PAGE_SIZE_OPTIONS,
  formatDateTime,
  type ArticleListItem,
  type ArticleStatus,
} from '@project/shared'

import { articleApi } from '@/api'

const loading = ref(false)
const rows = ref<ArticleListItem[]>([])
const total = ref(0)
const query = reactive({
  page: 1,
  page_size: DEFAULT_PAGE_SIZE,
  keyword: '',
  status: undefined as ArticleStatus | undefined,
})

const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const form = reactive({
  title: '',
  slug: '',
  summary: '',
  content: '',
  status: 'draft' as ArticleStatus,
})

const isEdit = computed(() => editingId.value !== null)

const rules: FormRules<typeof form> = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
}

const statusOptions = Object.entries(ARTICLE_STATUS_MAP).map(([value, item]) => ({
  value: value as ArticleStatus,
  label: item.label,
}))

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

function openCreate() {
  editingId.value = null
  Object.assign(form, { title: '', slug: '', summary: '', content: '', status: 'draft' })
  dialogVisible.value = true
}

async function openEdit(row: ArticleListItem) {
  const detail = await articleApi.detail(row.id)
  editingId.value = detail.id
  Object.assign(form, {
    title: detail.title,
    slug: detail.slug ?? '',
    summary: detail.summary ?? '',
    content: detail.content ?? '',
    status: detail.status,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  const payload = {
    title: form.title,
    slug: form.slug || null,
    summary: form.summary || null,
    content: form.content || null,
    status: form.status,
  }
  try {
    if (isEdit.value && editingId.value !== null) {
      await articleApi.update(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await articleApi.create(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await fetchList()
  } finally {
    submitting.value = false
  }
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
  const confirmed = await ElMessageBox.confirm(`确定删除《${row.title}》吗？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).catch(() => false)
  if (!confirmed) return

  await articleApi.remove(row.id)
  ElMessage.success('已删除')
  await fetchList()
}

onMounted(fetchList)
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">文章管理</h2>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>新建文章
      </el-button>
    </div>

    <div class="card">
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

      <el-table v-loading="loading" :data="rows" stripe border>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
        <el-table-column prop="slug" label="Slug" min-width="160" show-overflow-tooltip />
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
            <el-button link type="primary" size="small" @click="openEdit(row as ArticleListItem)"
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

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑文章' : '新建文章'"
      width="720px"
      top="6vh"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="72px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="文章标题" />
        </el-form-item>
        <el-form-item label="Slug">
          <el-input v-model="form.slug" placeholder="留空自动生成，用于门户 URL" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input
            v-model="form.summary"
            type="textarea"
            :rows="2"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="form.content" type="textarea" :rows="10" placeholder="支持 Markdown" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio v-for="item in statusOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
