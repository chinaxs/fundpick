<script setup lang="ts">
/** 会员区二级导航：概览 / 关注 / 持仓 各自独立页面，避免挤在一页里。 */
const route = useRoute()

const items = [
  { label: '工作台概览', to: '/dashboard', icon: '▤' },
  { label: '我的关注', to: '/favorites', icon: '☆' },
  { label: '持仓与交易', to: '/positions', icon: '◈' },
]
</script>

<template>
  <nav class="member-nav" aria-label="会员中心导航">
    <NuxtLink
      v-for="item in items"
      :key="item.to"
      :to="item.to"
      class="member-nav__item"
      :class="{
        'member-nav__item--active':
          route.path === item.to ||
          (item.to === '/positions' && route.path.startsWith('/portfolio/')),
      }"
    >
      <span class="member-nav__icon" aria-hidden="true">{{ item.icon }}</span>
      {{ item.label }}
    </NuxtLink>
    <NuxtLink to="/profile" class="member-nav__profile">个人中心 →</NuxtLink>
  </nav>
</template>

<style scoped>
.member-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  padding: 6px;
  margin: 18px 0 22px;
  background: var(--bg-soft);
  border: 1px solid var(--line-soft);
  border-radius: 12px;
}

.member-nav__item {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  height: 34px;
  padding: 0 14px;
  font-size: 13px;
  color: var(--ink-2);
  border-radius: 8px;
  transition: all 0.15s ease;
}

.member-nav__item:hover {
  color: var(--brand);
  background: #fff;
}

.member-nav__item--active {
  font-weight: 600;
  color: var(--brand);
  background: #fff;
  box-shadow: var(--shadow-xs);
}

.member-nav__icon {
  font-size: 14px;
  color: var(--muted-2);
}

.member-nav__item--active .member-nav__icon {
  color: var(--brand);
}

.member-nav__profile {
  margin-left: auto;
  padding: 0 12px;
  font-size: 12.5px;
  color: var(--muted);
}

.member-nav__profile:hover {
  color: var(--brand);
}

@media (max-width: 560px) {
  .member-nav__profile {
    display: none;
  }

  .member-nav__item {
    flex: 1;
    justify-content: center;
    padding: 0 8px;
    font-size: 12px;
  }
}
</style>
