<script setup lang="ts">
import type { ArticleListItem } from '@project/shared'
import { formatDate } from '@project/shared'

const props = defineProps<{ article: ArticleListItem }>()

const cover = computed(() => props.article.cover_url || '')
</script>

<template>
  <NuxtLink :to="`/articles/${article.slug}`" class="card">
    <div class="card__cover">
      <img v-if="cover" :src="cover" :alt="article.title" loading="lazy" />
      <span v-else class="card__placeholder">Study</span>
    </div>

    <div class="card__body">
      <h3 class="card__title">{{ article.title }}</h3>
      <p class="card__summary">{{ article.summary || '暂无摘要' }}</p>
      <div class="card__meta">
        <span>{{ formatDate(article.published_at) }}</span>
        <span>阅读 {{ article.view_count }}</span>
      </div>
    </div>
  </NuxtLink>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
}

.card__cover {
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: linear-gradient(135deg, #2b6cb0, #1a202c);
}

.card__cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card__placeholder {
  display: grid;
  place-items: center;
  height: 100%;
  font-size: 20px;
  font-weight: 700;
  color: rgb(255 255 255 / 70%);
  letter-spacing: 0.2em;
}

.card__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  padding: 18px 20px 20px;
}

.card__title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  line-height: 1.5;
}

.card__summary {
  flex: 1;
  margin: 0;
  font-size: 14px;
  color: var(--color-text-muted);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card__meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #a0aec0;
}
</style>
