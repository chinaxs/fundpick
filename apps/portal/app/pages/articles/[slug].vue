<script setup lang="ts">
import { formatDate, renderMarkdown } from '@project/shared'

const route = useRoute()
const slug = String(route.params.slug)

const { data: article } = await useArticleDetail(slug)

if (!article.value) {
  throw createError({ statusCode: 404, statusMessage: '文章不存在', fatal: true })
}

// 与后台预览共用同一份渲染实现（packages/shared/utils/markdown.ts）
const html = computed(() => renderMarkdown(article.value?.content))

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

      <aside v-if="article?.origin === 'sync'" class="source">
        <p class="source__text">
          本文为快讯摘编，来源：<strong>{{ article.source_name || '公开行情源' }}</strong
          >。 版权归原作者及来源方所有，本站仅收录标题与摘要。
        </p>
        <a
          v-if="article.source_url"
          :href="article.source_url"
          target="_blank"
          rel="noopener noreferrer"
          class="source__link"
        >
          查看原文 →
        </a>
        <p class="source__note">内容仅为资讯摘编，不构成投资建议。</p>
      </aside>

      <p v-if="!article?.content" class="detail__brief">
        这是外部快讯的摘编卡片，完整内容请到来源网站阅读。
      </p>
      <div v-else class="prose" v-html="html" />
    </div>
  </article>
</template>

<style scoped>
.source {
  margin: 20px 0 24px;
  padding: 14px 16px;
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--ink-2);
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
}

.source__text {
  margin: 0;
}

.source__link {
  display: inline-block;
  margin-top: 6px;
  font-weight: 600;
  color: var(--brand);
}

.source__link:hover {
  text-decoration: underline;
}

.source__note {
  margin: 4px 0 0;
  font-size: 11.5px;
  color: var(--muted-2);
}

.detail__brief {
  padding: 24px;
  font-size: 13px;
  color: var(--muted);
  text-align: center;
  background: var(--bg-soft);
  border: 1px dashed var(--line);
  border-radius: var(--radius-sm);
}

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
