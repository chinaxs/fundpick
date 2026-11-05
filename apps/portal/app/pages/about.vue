<script setup lang="ts">
useSeoMeta({
  title: '关于',
  description: 'Study 门户是一个前后端分离的内容平台示例：Nuxt 门户 + Vue 后台 + FastAPI 服务。',
})

const stack = [
  { name: '门户', detail: 'Nuxt 4 · SSR · SEO' },
  { name: '后台', detail: 'Vue 3 · Vite · Element Plus' },
  { name: '服务', detail: 'FastAPI · SQLAlchemy 2.x' },
  { name: '数据', detail: 'MySQL 8+ · Alembic 迁移' },
]
</script>

<template>
  <div class="section">
    <div class="container about">
      <h1 class="about__title">关于 Study 门户</h1>
      <p class="about__lead">
        这是一个可直接演进为企业官网 / 内容门户的工程骨架。门户负责展示，后台负责维护，
        服务端负责数据与权限，三者通过统一的接口契约协作。
      </p>

      <div class="stack">
        <div v-for="item in stack" :key="item.name" class="stack__item">
          <div class="stack__name">{{ item.name }}</div>
          <div class="stack__detail">{{ item.detail }}</div>
        </div>
      </div>

      <h2 class="about__h2">目录约定</h2>
      <pre class="tree">
apps/
  admin/     后台管理（Vue SPA）
  portal/    门户网站（Nuxt SSR）
packages/
  shared/    前后端共享类型与工具
services/
  api/       FastAPI 服务</pre>

      <h2 class="about__h2">下一步</h2>
      <ul class="about__list">
        <li>在后台创建文章，门户会自动展示已发布内容</li>
        <li>按业务新增模型：models → schemas → repository → service → router</li>
        <li>用 <code>make revision m="xxx"</code> 生成迁移，保持数据库版本可控</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.about {
  max-width: 780px;
}

.about__title {
  margin: 0;
  font-size: clamp(28px, 4vw, 40px);
  letter-spacing: -0.02em;
}

.about__lead {
  margin: 18px 0 0;
  font-size: 16px;
  line-height: 1.9;
  color: var(--color-text-muted);
}

.stack {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 16px;
  margin: 40px 0;
}

.stack__item {
  padding: 18px;
  background: var(--color-bg-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.stack__name {
  font-size: 13px;
  color: var(--color-text-muted);
}

.stack__detail {
  margin-top: 6px;
  font-size: 15px;
  font-weight: 600;
}

.about__h2 {
  margin: 40px 0 12px;
  font-size: 20px;
}

.tree {
  padding: 18px 20px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.9;
  color: #cbd5e0;
  background: #1a202c;
  border-radius: var(--radius);
}

.about__list {
  padding-left: 20px;
  line-height: 2.1;
  color: var(--color-text-muted);
}

.about__list code {
  padding: 2px 6px;
  background: #eef2f7;
  border-radius: 4px;
}
</style>
