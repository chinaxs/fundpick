<script setup lang="ts">
import { computed } from 'vue'

import { ARTICLE_CATEGORY_MAP, formatDate, renderMarkdown } from '@project/shared'

/** 发布前预览：与门户详情页共用同一份 Markdown 渲染，避免"预览和线上不一样"。 */
const props = defineProps<{
  modelValue: boolean
  title: string
  summary?: string | null
  content?: string | null
  category: string
  sourceName?: string | null
  sourceUrl?: string | null
  status?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const html = computed(() => renderMarkdown(props.content))
const categoryLabel = computed(() => ARTICLE_CATEGORY_MAP[props.category]?.label ?? props.category)
</script>

<template>
  <el-dialog v-model="visible" title="发布预览" width="760px" top="6vh">
    <div class="preview">
      <div class="preview__bar">
        <el-tag size="small" effect="light">{{ categoryLabel }}</el-tag>
        <el-tag v-if="status === 'draft'" size="small" type="warning" effect="light">草稿</el-tag>
        <span class="muted">{{ formatDate(new Date().toISOString()) }} · 预览不会增加阅读数</span>
      </div>
      <h1 class="preview__title">{{ title || '（未填写标题）' }}</h1>
      <p v-if="summary" class="preview__summary">{{ summary }}</p>
      <p v-if="sourceName" class="preview__source">
        摘编自 {{ sourceName }}
        <a v-if="sourceUrl" :href="sourceUrl" target="_blank" rel="noopener noreferrer">查看原文</a>
      </p>
      <div v-if="content" class="preview__body" v-html="html" />
      <p v-else class="preview__empty">
        正文为空：外部快讯只保留标题与摘要，请到来源网站阅读全文。
      </p>
      <p class="preview__footer">本页内容不构成投资建议。预览仅用于发布前核对排版与措辞。</p>
    </div>
  </el-dialog>
</template>

<style scoped lang="scss">
.preview {
  padding: 0 8px 8px;

  &__bar {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 18px;
  }

  &__title {
    margin: 0 0 10px;
    font-size: 26px;
    line-height: 1.35;
  }

  &__summary {
    margin: 0 0 12px;
    font-size: 15px;
    line-height: 1.8;
    color: $text-regular;
  }

  &__source {
    margin: 0 0 18px;
    font-size: 12.5px;
    color: $text-secondary;

    a {
      margin-left: 8px;
      color: $color-primary;
    }
  }

  &__body {
    font-size: 15px;
    line-height: 1.9;

    :deep(h1),
    :deep(h2),
    :deep(h3) {
      margin: 22px 0 10px;
      line-height: 1.4;
    }

    :deep(p) {
      margin: 0 0 14px;
    }

    :deep(code) {
      padding: 1px 5px;
      font-size: 13px;
      background: #f1f5f9;
      border-radius: 4px;
    }
  }

  &__empty {
    padding: 20px;
    font-size: 14px;
    color: $text-secondary;
    background: #f8fafc;
    border-radius: 8px;
  }

  &__footer {
    padding-top: 16px;
    margin-top: 24px;
    font-size: 12px;
    color: $text-secondary;
    border-top: 1px solid $border-color;
  }
}

.muted {
  font-size: 12.5px;
  color: $text-secondary;
}
</style>
