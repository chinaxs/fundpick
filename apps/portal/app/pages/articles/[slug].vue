<script setup lang="ts">
import { formatDate } from '@project/shared'

const route = useRoute()
const slug = String(route.params.slug)

const { data: article } = await useArticleDetail(slug)

if (!article.value) {
  throw createError({ statusCode: 404, statusMessage: '文章不存在', fatal: true })
}

// 简易 Markdown 渲染：标题、加粗、代码块、段落、换行
const html = computed(() => {
  const source = article.value?.content ?? ''
  const escaped = source.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  return escaped
    .replace(/^### (.*)$/gm, '<h3>$1</h3>')
    .replace(/^## (.*)$/gm, '<h2>$1</h2>')
    .replace(/^# (.*)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .split(/\n{2,}/)
    .map((block) =>
      block.trim().startsWith('<h') ? block : `<p>${block.replace(/\n/g, '<br />')}</p>`,
    )
    .join('\n')
})

useSeoMeta({
  title: () => article.value?.title ?? '文章',
  description: () => article.value?.summary ?? undefined,
})
</script>

<template>
  <article class="detail">
    <div class="container detail__inner">
      <NuxtLink to="/articles" class="back">← 返回列表</NuxtLink>

      <h1 class="detail__title">{{ article?.title }}</h1>
      <div class="detail__meta">
        <span>{{ formatDate(article?.published_at) }}</span>
        <span>阅读 {{ article?.view_count ?? 0 }}</span>
      </div>

      <p v-if="article?.summary" class="detail__summary">{{ article.summary }}</p>

      <div class="prose" v-html="html" />
    </div>
  </article>
</template>

<style scoped>
.detail {
  padding: 40px 0 24px;
}

.detail__inner {
  max-width: 780px;
}

.back {
  font-size: 14px;
  color: var(--color-text-muted);
}

.back:hover {
  color: var(--color-primary);
}

.detail__title {
  margin: 24px 0 12px;
  font-size: clamp(26px, 3.6vw, 36px);
  line-height: 1.3;
  letter-spacing: -0.01em;
}

.detail__meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #a0aec0;
}

.detail__summary {
  padding: 16px 20px;
  margin: 24px 0;
  font-size: 15px;
  color: var(--color-text-muted);
  background: var(--color-bg-soft);
  border-left: 3px solid var(--color-primary);
  border-radius: 6px;
}
</style>
