<script setup lang="ts">
const route = useRoute()

const params = computed(() => ({
  page: Number(route.query.page ?? 1) || 1,
  page_size: 6,
}))

const { data, pending } = await useArticleList(params)

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
          <p class="section__desc">共 {{ data?.total ?? 0 }} 篇内容</p>
        </div>
      </div>

      <div v-if="pending" class="loading">加载中…</div>

      <div v-else class="grid">
        <ArticleCard v-for="item in data?.items ?? []" :key="item.id" :article="item" />
      </div>

      <p v-if="!pending && !data?.items?.length" class="empty">暂无已发布内容</p>

      <nav v-if="totalPages > 1" class="pager">
        <NuxtLink
          v-if="(params.page ?? 1) > 1"
          :to="{ path: '/articles', query: { page: (params.page ?? 1) - 1 } }"
          class="pager__btn"
        >
          上一页
        </NuxtLink>
        <span class="pager__info">{{ params.page }} / {{ totalPages }}</span>
        <NuxtLink
          v-if="(params.page ?? 1) < totalPages"
          :to="{ path: '/articles', query: { page: (params.page ?? 1) + 1 } }"
          class="pager__btn"
        >
          下一页
        </NuxtLink>
      </nav>
    </div>
  </div>
</template>

<style scoped>
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
