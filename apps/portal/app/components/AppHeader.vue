<script setup lang="ts">
const navs = [
  { label: '首页', to: '/' },
  { label: '资讯', to: '/articles' },
  { label: '关于', to: '/about' },
]

const menuOpen = ref(false)
</script>

<template>
  <header class="header">
    <div class="container header__inner">
      <NuxtLink to="/" class="brand">
        <span class="brand__mark">S</span>
        <span class="brand__name">Study 门户</span>
      </NuxtLink>

      <nav class="nav" :class="{ 'nav--open': menuOpen }">
        <NuxtLink
          v-for="item in navs"
          :key="item.to"
          :to="item.to"
          class="nav__link"
          @click="menuOpen = false"
        >
          {{ item.label }}
        </NuxtLink>
      </nav>

      <div class="header__actions">
        <a class="header__admin" href="http://localhost:5174" target="_blank" rel="noreferrer">
          管理后台
        </a>
        <button class="burger" type="button" @click="menuOpen = !menuOpen">
          <span />
          <span />
          <span />
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgb(255 255 255 / 88%);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--color-border);
}

.header__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
}

.brand {
  display: flex;
  gap: 10px;
  align-items: center;
  font-weight: 700;
}

.brand__mark {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  font-size: 16px;
  color: #fff;
  background: var(--color-primary);
  border-radius: 9px;
}

.nav {
  display: flex;
  gap: 28px;
}

.nav__link {
  font-size: 15px;
  color: var(--color-text-muted);
  transition: color 0.15s ease;
}

.nav__link:hover,
.nav__link.router-link-active {
  color: var(--color-primary);
}

.header__actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.header__admin {
  padding: 8px 16px;
  font-size: 14px;
  color: var(--color-primary);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  transition: background 0.15s ease;
}

.header__admin:hover {
  background: var(--color-bg-soft);
}

.burger {
  display: none;
  flex-direction: column;
  gap: 4px;
  padding: 6px;
  cursor: pointer;
  background: none;
  border: none;
}

.burger span {
  display: block;
  width: 20px;
  height: 2px;
  background: var(--color-text);
}

@media (max-width: 768px) {
  .burger {
    display: flex;
  }

  .nav {
    position: absolute;
    top: 64px;
    right: 0;
    left: 0;
    display: none;
    flex-direction: column;
    gap: 0;
    padding: 8px 20px 16px;
    background: #fff;
    border-bottom: 1px solid var(--color-border);
  }

  .nav--open {
    display: flex;
  }

  .nav__link {
    padding: 10px 0;
  }

  .header__admin {
    display: none;
  }
}
</style>
