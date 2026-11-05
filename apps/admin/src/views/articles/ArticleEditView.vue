<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  ARTICLE_STATUS_MAP,
  formatDateTime,
  type Article,
  type ArticleStatus,
} from '@project/shared'

import { articleApi } from '@/api'

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

const form = reactive({
  title: '',
  slug: '',
  summary: '',
  content: '',
  status: 'draft' as ArticleStatus,
})

const rules: FormRules<typeof form> = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
}

const statusOptions = Object.entries(ARTICLE_STATUS_MAP).map(([value, item]) => ({
  value: value as ArticleStatus,
  label: item.label,
}))

const isEdit = computed(() => editingId.value !== null)

onMounted(async () => {
  if (!editingId.value) return
  loading.value = true
  try {
    detail.value = await articleApi.detail(editingId.value)
    Object.assign(form, {
      title: detail.value.title,
      slug: detail.value.slug ?? '',
      summary: detail.value.summary ?? '',
      content: detail.value.content ?? '',
      status: detail.value.status,
    })
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
    status: status ?? form.status,
  }
  try {
    if (isEdit.value && editingId.value !== null) {
      await articleApi.update(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await articleApi.create(payload)
      ElMessage.success('已创建')
    }
    router.push({ name: 'articles' })
  } finally {
    submitting.value = false
  }
}

function handleCancel() {
  if (form.title && form.content) {
    ElMessage.info('已放弃未保存的修改')
  }
  router.push({ name: 'articles' })
}
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">{{ isEdit ? '编辑文章' : '新建文章' }}</h2>
      <div class="header-actions">
        <el-button @click="handleCancel">返回列表</el-button>
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
            <el-form-item label="状态">
              <el-radio-group v-model="form.status">
                <el-radio v-for="item in statusOptions" :key="item.value" :value="item.value">
                  {{ item.label }}
                </el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>

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
  </div>
</template>

<style scoped lang="scss">
.header-actions {
  display: flex;
  gap: 12px;
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
