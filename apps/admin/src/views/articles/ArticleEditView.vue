<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  ARTICLE_CATEGORY_MAP,
  ARTICLE_STATUS_MAP,
  formatDateTime,
  type Article,
  type ArticleStatus,
} from '@project/shared'

import { articleApi } from '@/api'
import ArticlePreviewDialog from '@/components/article/ArticlePreviewDialog.vue'
import ArticleVersionDrawer from '@/components/article/ArticleVersionDrawer.vue'

/** 独立编辑页：列表页只负责跳转，编辑在整页完成（长文编辑弹窗太挤） */
const route = useRoute()
const router = useRouter()

const editingId = computed(() => {
  const id = Number(route.params.id)
  return Number.isFinite(id) && id > 0 ? id : null
})

const formRef = ref<FormInstance>()
const loading = ref(false)
const submitting = ref(false)
const detail = ref<Article | null>(null)
const previewVisible = ref(false)
const versionsVisible = ref(false)
const savedSnapshot = ref('')

interface ArticleDraft {
  title: string
  slug: string
  summary: string
  content: string
  category: string
  source_name: string
  source_url: string
  status: ArticleStatus
}

const form = reactive<ArticleDraft>({
  title: '',
  slug: '',
  summary: '',
  content: '',
  category: 'market',
  source_name: '',
  source_url: '',
  status: 'draft',
})

const rules: FormRules<typeof form> = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
}

const statusOptions = Object.entries(ARTICLE_STATUS_MAP).map(([value, item]) => ({
  value: value as ArticleStatus,
  label: item.label,
}))
const categoryOptions = Object.entries(ARTICLE_CATEGORY_MAP).map(([value, item]) => ({
  value,
  label: item.label,
}))

const isEdit = computed(() => editingId.value !== null)
/** 有未保存改动：只比这几项会被提交的字段 */
const dirty = computed(() => JSON.stringify(payloadOf()) !== savedSnapshot.value)

function payloadOf(): ArticleDraft {
  return {
    title: form.title.trim(),
    slug: form.slug.trim(),
    summary: form.summary.trim(),
    content: form.content,
    category: form.category,
    source_name: form.source_name.trim(),
    source_url: form.source_url.trim(),
    status: form.status,
  }
}

function markSaved() {
  savedSnapshot.value = JSON.stringify(payloadOf())
}

function applyDetail(article: Article) {
  detail.value = article
  Object.assign(form, {
    title: article.title,
    slug: article.slug ?? '',
    summary: article.summary ?? '',
    content: article.content ?? '',
    category: article.category ?? 'market',
    source_name: article.source_name ?? '',
    source_url: article.source_url ?? '',
    status: article.status,
  })
  markSaved()
}

onMounted(async () => {
  if (!editingId.value) {
    markSaved()
    return
  }
  loading.value = true
  try {
    applyDetail(await articleApi.detail(editingId.value))
  } finally {
    loading.value = false
  }
})

async function handleSubmit(status?: ArticleStatus) {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  const payload = {
    title: form.title,
    slug: form.slug || null,
    summary: form.summary || null,
    content: form.content || null,
    category: form.category,
    source_name: form.source_name || null,
    source_url: form.source_url || null,
    status: status ?? form.status,
  }
  try {
    if (isEdit.value && editingId.value !== null) {
      await articleApi.update(editingId.value, payload)
      ElMessage.success('已更新，历史版本已记录')
    } else {
      await articleApi.create(payload)
      ElMessage.success('已创建')
    }
    markSaved()
    router.push({ name: 'articles' })
  } finally {
    submitting.value = false
  }
}

async function handleCancel() {
  if (dirty.value) {
    try {
      await ElMessageBox.confirm('有未保存的修改，确认离开？', '放弃修改', {
        confirmButtonText: '离开',
        cancelButtonText: '继续编辑',
        type: 'warning',
      })
    } catch {
      return
    }
  }
  router.push({ name: 'articles' })
}

async function reloadAfterRestore() {
  if (!editingId.value) return
  loading.value = true
  try {
    applyDetail(await articleApi.detail(editingId.value))
    ElMessage.success('已恢复到所选版本')
  } finally {
    loading.value = false
  }
}

/** 路由离开拦截：刷新/关闭标签页由 beforeunload 兜底 */
onBeforeRouteLeave(async () => {
  if (!dirty.value || submitting.value) return true
  try {
    await ElMessageBox.confirm('有未保存的修改，确认离开？', '未保存的修改', {
      confirmButtonText: '离开',
      cancelButtonText: '继续编辑',
      type: 'warning',
    })
    return true
  } catch {
    return false
  }
})

function onBeforeUnload(event: BeforeUnloadEvent) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">
        {{ isEdit ? '编辑文章' : '新建文章' }}
        <span v-if="dirty" class="dirty">未保存</span>
      </h2>
      <div class="header-actions">
        <el-button @click="handleCancel">返回列表</el-button>
        <el-button v-if="isEdit" @click="versionsVisible = true">历史版本</el-button>
        <el-button @click="previewVisible = true">预览</el-button>
        <el-button
          v-if="form.status !== 'published'"
          :loading="submitting"
          type="success"
          plain
          @click="handleSubmit('published')"
        >
          直接发布
        </el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit()"> 保存 </el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="17">
        <div class="card">
          <el-skeleton v-if="loading" :rows="8" animated />
          <el-form
            v-else
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            size="large"
          >
            <el-form-item label="标题" prop="title">
              <el-input
                v-model="form.title"
                placeholder="文章标题"
                maxlength="200"
                show-word-limit
              />
            </el-form-item>
            <el-form-item label="Slug">
              <el-input v-model="form.slug" placeholder="留空自动生成，用于门户 URL" />
            </el-form-item>
            <el-form-item label="摘要">
              <el-input
                v-model="form.summary"
                type="textarea"
                :rows="3"
                maxlength="500"
                show-word-limit
                placeholder="列表页与分享卡片展示的摘要"
              />
            </el-form-item>
            <el-form-item label="正文（支持 Markdown）">
              <el-input
                v-model="form.content"
                type="textarea"
                :autosize="{ minRows: 16, maxRows: 32 }"
                placeholder="# 标题&#10;&#10;正文内容，支持 Markdown 语法"
                class="content-editor"
              />
            </el-form-item>
          </el-form>
        </div>
      </el-col>

      <el-col :xs="24" :lg="7">
        <div class="card side">
          <h3 class="section-title">发布设置</h3>
          <el-form label-position="top">
            <el-form-item label="分类">
              <el-select v-model="form.category" style="width: 100%">
                <el-option
                  v-for="item in categoryOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="来源名称">
              <el-input v-model="form.source_name" placeholder="转载或摘编时填写，如 财联社" />
            </el-form-item>
            <el-form-item label="原文链接">
              <el-input
                v-model="form.source_url"
                placeholder="粘贴原文链接，如 example.com/news/1"
              />
            </el-form-item>
            <el-form-item label="状态">
              <el-radio-group v-model="form.status">
                <el-radio v-for="item in statusOptions" :key="item.value" :value="item.value">
                  {{ item.label }}
                </el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>

          <p class="tip">
            外部快讯只保留标题、摘要与原文链接，不转载全文；发布前请核对来源与措辞。
          </p>

          <template v-if="detail">
            <el-divider />
            <h3 class="section-title">元信息</h3>
            <div class="meta">
              <div class="meta__row">
                <span class="muted">ID</span><span>{{ detail.id }}</span>
              </div>
              <div class="meta__row">
                <span class="muted">浏览量</span><span>{{ detail.view_count }}</span>
              </div>
              <div class="meta__row">
                <span class="muted">创建时间</span>
                <span>{{ formatDateTime(detail.created_at) }}</span>
              </div>
              <div class="meta__row">
                <span class="muted">更新时间</span>
                <span>{{ formatDateTime(detail.updated_at) }}</span>
              </div>
            </div>
          </template>
        </div>
      </el-col>
    </el-row>

    <ArticlePreviewDialog
      v-model="previewVisible"
      :title="form.title"
      :summary="form.summary"
      :content="form.content"
      :category="form.category"
      :source-name="form.source_name"
      :source-url="form.source_url"
      :status="form.status"
    />
    <ArticleVersionDrawer
      v-model="versionsVisible"
      :article-id="editingId"
      @restored="reloadAfterRestore"
    />
  </div>
</template>

<style scoped lang="scss">
.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.dirty {
  padding: 1px 8px;
  margin-left: 8px;
  font-size: 12px;
  font-weight: 400;
  color: $color-warning;
  vertical-align: middle;
  background: rgb(183 121 31 / 12%);
  border-radius: 999px;
}

.muted {
  font-size: 13px;
  color: $text-secondary;
}

.side {
  position: sticky;
  top: 12px;
}

.section-title {
  margin: 0 0 14px;
  font-size: 15px;
  font-weight: 600;
}

.tip {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: $text-secondary;
}

.meta__row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 13px;

  span:last-child {
    color: $text-primary;
  }
}

:deep(.content-editor textarea) {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  line-height: 1.7;
}
</style>
