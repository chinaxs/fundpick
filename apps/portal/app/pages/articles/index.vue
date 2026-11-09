<script setup lang="ts">
import { ARTICLE_CATEGORY_MAP } from '@project/shared'

const route = useRoute()

/** 分类从 URL 读，保证筛选链接可分享 */
const category = computed(() => {
  const value = String(route.query.category ?? '')
  return value in ARTICLE_CATEGORY_MAP ? value : ''
})

const TABS = [
  { value: '', label: '全部' },
  ...Object.entries(ARTICLE_CATEGORY_MAP).map(([value, item]) => ({
    value,
    label: item.label,
  })),
]

const params = computed(() => ({
  page: Number(route.query.page ?? 1) || 1,
  page_size: 6,
  category: category.value || undefined,
}))

const { data, pending } = await useArticleList(params)

/** NuxtLink 改的是 query，浏览器不会自动回顶；分页器在卡片下方，必须显式滚动 */
function onPageClick() {
  if (import.meta.client) window.scrollTo({ top: 0, behavior: 'smooth' })
}

const totalPages = computed(() => {
  if (!data.value) return 1
  return Math.max(1, Math.ceil(data.value.total / data.value.page_size))
})

useSeoMeta({
  title: '资讯',
  description: '拾贝市场观察：基金市场的结构性变化与数据解读。',
})
</script>

<template>
  <div class="section">
    <div class="container">
      <div class="section__head">
        <div>
          <h2 class="section__title">资讯</h2>
          <p class="section__desc">
            共 {{ data?.total ?? 0 }} 篇内容
            <template v-if="category"> · {{ ARTICLE_CATEGORY_MAP[category]?.label }}</template>
          </p>
        </div>
      </div>

      <nav class="tabs" aria-label="资讯分类">
        <NuxtLink
          v-for="tab in TABS"
          :key="tab.value"
          :to="{ path: '/articles', query: tab.value ? { category: tab.value } : {} }"
          class="tabs__btn"
          :class="{ 'is-active': category === tab.value }"
        >
          {{ tab.label }}
        </NuxtLink>
      </nav>

      <div v-if="pending" class="loading">加载中…</div>

      <div v-else class="grid">
        <ArticleCard v-for="item in data?.items ?? []" :key="item.id" :article="item" />
      </div>

      <p v-if="!pending && !data?.items?.length" class="empty">暂无已发布内容</p>

      <nav v-if="totalPages > 1" class="pager">
        <NuxtLink
          v-if="(params.page ?? 1) > 1"
          :to="{
            path: '/articles',
            query: { ...(category ? { category } : {}), page: (params.page ?? 1) - 1 },
          }"
          class="pager__btn"
          @click="onPageClick"
        >
          上一页
        </NuxtLink>
        <span class="pager__info">{{ params.page }} / {{ totalPages }}</span>
        <span v-if="pending" class="pager__loading">加载中…</span>
        <NuxtLink
          v-if="(params.page ?? 1) < totalPages"
          :to="{
            path: '/articles',
            query: { ...(category ? { category } : {}), page: (params.page ?? 1) + 1 },
          }"
          class="pager__btn"
          @click="onPageClick"
        >
          下一页
        </NuxtLink>
      </nav>
    </div>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 24px;
  overflow-x: auto;
  scrollbar-width: none;
}

.tabs::-webkit-scrollbar {
  display: none;
}

.tabs__btn {
  flex: none;
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 999px;
  transition:
    color 0.15s ease,
    background 0.15s ease;
}

.tabs__btn:hover {
  color: var(--ink);
  border-color: var(--muted-2);
}

.tabs__btn.is-active {
  color: var(--brand);
  background: var(--brand-soft);
  border-color: transparent;
}

.pager__loading {
  font-size: 12.5px;
  color: var(--brand);
  animation: pager-pulse 1.2s ease-in-out infinite;
}

@keyframes pager-pulse {
  50% {
    opacity: 0.4;
  }
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
  min-height: 120px;
}

.empty {
  padding: 48px;
  color: var(--color-text-muted);
  text-align: center;
  background: var(--color-bg-soft);
  border-radius: var(--radius);
}

.loading {
  padding: 48px;
  color: var(--color-text-muted);
  text-align: center;
}

.pager {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: center;
  margin-top: 40px;
}

.pager__btn {
  padding: 8px 18px;
  font-size: 14px;
  color: var(--color-primary);
  border: 1px solid var(--color-border);
  border-radius: 999px;
}

.pager__btn:hover {
  background: var(--color-bg-soft);
}

.pager__info {
  font-size: 14px;
  color: var(--color-text-muted);
}
</style>
