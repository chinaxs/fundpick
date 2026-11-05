<script setup lang="ts">
const { data: latest } = await useArticleList({ page: 1, page_size: 3 })

useSeoMeta({
  title: '首页',
  description: 'Study 门户：面向企业的一站式内容与解决方案平台，提供产品介绍、行业洞察与最新资讯。',
  ogTitle: 'Study 门户',
  ogDescription: '产品介绍、行业洞察与最新资讯',
})

const features = [
  {
    title: '服务端渲染',
    desc: '基于 Nuxt SSR，首屏直出、SEO 友好，搜索引擎可完整抓取内容。',
    icon: '⚡',
  },
  {
    title: '内容集中管理',
    desc: '后台维护文章与状态，门户实时读取接口，草稿与发布分离。',
    icon: '🗂️',
  },
  {
    title: '工程化基础',
    desc: 'monorepo 统一管理前端与后端依赖，类型定义前后端共享。',
    icon: '🧩',
  },
]
</script>

<template>
  <div>
    <section class="hero">
      <div class="container hero__inner">
        <span class="hero__badge">Nuxt 4 · SSR · TypeScript</span>
        <h1 class="hero__title">把内容变成<br />可被看见的资产</h1>
        <p class="hero__desc">
          Study 门户专注企业内容展示：产品介绍、行业洞察、公司动态，一处维护、多端呈现，
          并为搜索引擎做好充分准备。
        </p>
        <div class="hero__actions">
          <NuxtLink to="/articles" class="btn">浏览资讯</NuxtLink>
          <NuxtLink to="/about" class="btn btn--ghost">了解我们</NuxtLink>
        </div>

        <dl class="hero__stats">
          <div>
            <dt>内容更新</dt>
            <dd>实时同步</dd>
          </div>
          <div>
            <dt>首屏渲染</dt>
            <dd>&lt; 1s</dd>
          </div>
          <div>
            <dt>移动端适配</dt>
            <dd>全响应式</dd>
          </div>
        </dl>
      </div>
    </section>

    <section class="section section--soft">
      <div class="container">
        <div class="section__head">
          <div>
            <h2 class="section__title">为什么选择这套架构</h2>
            <p class="section__desc">前后端分离，门户与后台共享同一套数据与类型定义</p>
          </div>
        </div>

        <div class="features">
          <div v-for="item in features" :key="item.title" class="feature">
            <span class="feature__icon">{{ item.icon }}</span>
            <h3 class="feature__title">{{ item.title }}</h3>
            <p class="feature__desc">{{ item.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <div class="section__head">
          <div>
            <h2 class="section__title">最新资讯</h2>
            <p class="section__desc">来自后台发布的实时内容</p>
          </div>
          <NuxtLink to="/articles" class="section__more">查看全部 →</NuxtLink>
        </div>

        <div v-if="latest?.items?.length" class="grid">
          <ArticleCard v-for="item in latest.items" :key="item.id" :article="item" />
        </div>
        <p v-else class="empty">暂无已发布内容，请在后台发布文章后刷新。</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  color: #fff;
  background:
    radial-gradient(900px 400px at 80% -10%, rgb(43 108 176 / 55%), transparent 60%),
    linear-gradient(160deg, #1a202c 0%, #1f3a5f 100%);
}

.hero__inner {
  padding: 96px 20px 80px;
}

.hero__badge {
  display: inline-block;
  padding: 6px 14px;
  font-size: 12px;
  letter-spacing: 0.08em;
  color: #bee3f8;
  background: rgb(255 255 255 / 8%);
  border: 1px solid rgb(255 255 255 / 14%);
  border-radius: 999px;
}

.hero__title {
  margin: 20px 0 0;
  font-size: clamp(32px, 5vw, 52px);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.hero__desc {
  max-width: 560px;
  margin: 20px 0 0;
  font-size: 16px;
  line-height: 1.9;
  color: #cbd5e0;
}

.hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 32px;
}

.hero__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 48px;
  margin: 56px 0 0;
}

.hero__stats dt {
  font-size: 13px;
  color: #a0aec0;
}

.hero__stats dd {
  margin: 4px 0 0;
  font-size: 20px;
  font-weight: 600;
}

.features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
}

.feature {
  padding: 28px 24px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.feature__icon {
  font-size: 22px;
}

.feature__title {
  margin: 14px 0 8px;
  font-size: 17px;
}

.feature__desc {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: var(--color-text-muted);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
}

.section__more {
  font-size: 14px;
  color: var(--color-primary);
}

.empty {
  padding: 40px;
  color: var(--color-text-muted);
  text-align: center;
  background: var(--color-bg-soft);
  border-radius: var(--radius);
}
</style>
