<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { articleApi, userApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const stats = ref({ users: 0, articles: 0, published: 0 })
const loading = ref(true)

onMounted(async () => {
  try {
    const [users, articles, published] = await Promise.all([
      userApi.list({ page: 1, page_size: 1 }),
      articleApi.list({ page: 1, page_size: 1 }),
      articleApi.list({ page: 1, page_size: 1, status: 'published' }),
    ])
    stats.value = {
      users: users.total,
      articles: articles.total,
      published: published.total,
    }
  } finally {
    loading.value = false
  }
})

const cards = [
  { key: 'users', label: '用户总数', icon: 'User', to: 'users' },
  { key: 'articles', label: '文章总数', icon: 'Document', to: 'articles' },
  { key: 'published', label: '已发布', icon: 'Promotion', to: 'articles' },
] as const
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">仪表盘</h2>
      <span class="muted">欢迎回来，{{ authStore.displayName }}</span>
    </div>

    <el-row :gutter="16">
      <el-col v-for="card in cards" :key="card.key" :xs="24" :sm="8">
        <div class="card stat" @click="router.push({ name: card.to })">
          <div class="stat__icon">
            <el-icon :size="22"><component :is="card.icon" /></el-icon>
          </div>
          <div>
            <div class="stat__label">{{ card.label }}</div>
            <div class="stat__value">
              <el-skeleton v-if="loading" :rows="0" animated style="width: 60px" />
              <template v-else>{{ stats[card.key] }}</template>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="card">
      <h3 class="section-title">项目结构速览</h3>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="前端（后台）"
          >apps/admin · Vue 3 + Vite + Element Plus</el-descriptions-item
        >
        <el-descriptions-item label="前端（门户）">apps/portal · Nuxt（SSR）</el-descriptions-item>
        <el-descriptions-item label="后端"
          >services/api · FastAPI + SQLAlchemy 2.x</el-descriptions-item
        >
        <el-descriptions-item label="数据库">MySQL · test_study</el-descriptions-item>
        <el-descriptions-item label="共享层">packages/shared · 类型与常量</el-descriptions-item>
        <el-descriptions-item label="接口文档">
          <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">/docs</a>
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </div>
</template>

<style scoped lang="scss">
.muted {
  font-size: 13px;
  color: $text-secondary;
}

.stat {
  display: flex;
  gap: 14px;
  align-items: center;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgb(16 24 40 / 8%);
  }

  &__icon {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    color: $color-primary;
    background: rgb(43 108 176 / 10%);
    border-radius: 10px;
  }

  &__label {
    font-size: 13px;
    color: $text-secondary;
  }

  &__value {
    margin-top: 4px;
    font-size: 24px;
    font-weight: 600;
    line-height: 1.2;
  }
}

.section-title {
  margin: 0 0 16px;
  font-size: 15px;
  font-weight: 600;
}
</style>
