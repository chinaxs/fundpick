<script setup lang="ts">
import { ElMessage } from 'element-plus'

const navs = [
  { label: '首页', to: '/' },
  { label: '基金筛选', to: '/funds' },
  { label: '研报', to: '/articles' },
  { label: '关于', to: '/about' },
]

const menuOpen = ref(false)

const { isLoggedIn, displayName, avatarText, user, openAuth, logout } = useAuth()
const { count: favCount, load: loadFavorites } = useFavorites()

// 登录后拉一次，用于菜单里显示关注数量
watch(
  isLoggedIn,
  (v) => {
    if (v) loadFavorites()
  },
  { immediate: true },
)

async function handleCommand(command: string) {
  if (command === 'favorites') {
    await navigateTo('/favorites')
    return
  }
  if (command === 'logout') {
    await logout()
    useFavorites().reset()
    ElMessage.success('已退出登录')
  }
}
</script>

<template>
  <header class="header">
    <div class="container header__inner">
      <NuxtLink to="/" class="brand">
        <BrandMark :size="32" class="brand__mark" />
        <span class="brand__name">拾贝</span>
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
        <!-- 已登录：头像下拉 -->
        <el-dropdown v-if="isLoggedIn" trigger="click" @command="handleCommand">
          <button type="button" class="user">
            <span class="user__avatar">{{ avatarText }}</span>
            <span class="user__name">{{ displayName }}</span>
            <el-icon class="user__caret"><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>
                {{ user?.email || user?.username }}
              </el-dropdown-item>
              <el-dropdown-item divided command="favorites">
                我的关注（{{ favCount }}）
              </el-dropdown-item>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <!-- 未登录：登录 / 注册 -->
        <template v-else>
          <button type="button" class="btn-ghost" @click="openAuth('login')">登录</button>
          <button type="button" class="btn-solid" @click="openAuth('register')">免费注册</button>
        </template>

        <button
          class="burger"
          type="button"
          :aria-expanded="menuOpen"
          aria-label="切换菜单"
          @click="menuOpen = !menuOpen"
        >
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
  border-bottom: 1px solid var(--line);
}

.header__inner {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  height: 64px;
}

.brand {
  display: flex;
  gap: 10px;
  align-items: center;
  font-weight: 700;
  white-space: nowrap;
}

.brand__mark {
  color: var(--brand);
}

.nav {
  display: flex;
  gap: 28px;
  margin-right: auto;
  margin-left: 24px;
}

.nav__link {
  font-size: 15px;
  color: var(--muted);
  transition: color 0.15s ease;
}

.nav__link:hover,
.nav__link.router-link-active {
  color: var(--brand);
}

.header__actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

/* ---- 登录 / 注册 ---- */
.btn-ghost,
.btn-solid {
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  border-radius: 999px;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}

.btn-ghost {
  color: var(--ink-2);
  background: transparent;
  border: 1px solid var(--line);
}

.btn-ghost:hover {
  color: var(--brand);
  border-color: var(--brand);
}

.btn-solid {
  color: #fff;
  background: var(--brand);
  border: 1px solid var(--brand);
}

.btn-solid:hover {
  background: var(--brand-dark);
  border-color: var(--brand-dark);
}

/* ---- 用户头像 ---- */
.user {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 4px 12px 4px 4px;
  cursor: pointer;
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: 999px;
  transition: border-color 0.15s ease;
}

.user:hover {
  border-color: var(--brand);
}

.user__avatar {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: var(--brand);
  border-radius: 50%;
}

.user__name {
  max-width: 96px;
  overflow: hidden;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user__caret {
  font-size: 12px;
  color: var(--muted-2);
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
  background: var(--ink-2);
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
    margin: 0;
    padding: 8px 20px 16px;
    background: #fff;
    border-bottom: 1px solid var(--line);
  }

  .nav--open {
    display: flex;
  }

  .nav__link {
    padding: 10px 0;
  }

  /* 移动端只留注册按钮，登录从菜单进 */
  .btn-ghost {
    display: none;
  }

  .user__name,
  .user__caret {
    display: none;
  }

  .user {
    padding: 4px;
  }
}
</style>
