<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'

import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const authStore = useAuthStore()

const menus = [
  { name: 'dashboard', title: '仪表盘', icon: 'Odometer' },
  { name: 'users', title: '用户管理', icon: 'User' },
  { name: 'articles', title: '文章管理', icon: 'Document' },
]

const activeMenu = computed(() => route.name as string)

onMounted(() => {
  // 页面刷新后恢复用户信息
  authStore.fetchProfile().catch(() => authStore.logout())
})

async function handleLogout() {
  const confirmed = await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    type: 'warning',
    confirmButtonText: '退出',
    cancelButtonText: '取消',
  }).catch(() => false)
  if (!confirmed) return

  authStore.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <el-container class="layout">
    <el-aside :width="appStore.sidebarCollapsed ? '64px' : '220px'" class="layout__aside">
      <div class="logo">
        <span class="logo__mark">S</span>
        <span v-show="!appStore.sidebarCollapsed" class="logo__text">Study Admin</span>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="appStore.sidebarCollapsed"
        :collapse-transition="false"
        router
        class="layout__menu"
      >
        <el-menu-item v-for="item in menus" :key="item.name" :index="item.name">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="layout__header">
        <div class="layout__header-left">
          <el-icon class="collapse-btn" @click="appStore.toggleSidebar()">
            <Fold v-if="!appStore.sidebarCollapsed" />
            <Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ name: 'dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta.title">{{ route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <el-dropdown trigger="click">
          <span class="user">
            <el-avatar :size="30">{{ authStore.displayName.slice(0, 1) }}</el-avatar>
            <span class="user__name">{{ authStore.displayName }}</span>
            <el-icon><CaretBottom /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>{{
                authStore.currentUser?.email ?? '—'
              }}</el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="layout__main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped lang="scss">
.layout {
  height: 100%;

  &__aside {
    display: flex;
    flex-direction: column;
    background: #1f2937;
    transition: width 0.2s ease;
    overflow: hidden;
  }

  &__menu {
    flex: 1;
    border-right: none;
    background: transparent;

    :deep(.el-menu-item) {
      color: #cbd5e0;

      &:hover {
        background: rgb(255 255 255 / 8%);
        color: #fff;
      }

      &.is-active {
        background: $color-primary;
        color: #fff;
      }
    }
  }

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: $header-height;
    padding: 0 20px;
    background: $bg-container;
    border-bottom: 1px solid $border-color;
  }

  &__header-left {
    display: flex;
    gap: 16px;
    align-items: center;
  }

  &__main {
    padding: 20px;
    background: $bg-page;
  }
}

.logo {
  display: flex;
  gap: 10px;
  align-items: center;
  height: $header-height;
  padding: 0 16px;
  overflow: hidden;
  white-space: nowrap;

  &__mark {
    display: grid;
    flex: none;
    place-items: center;
    width: 32px;
    height: 32px;
    font-weight: 700;
    color: #fff;
    background: $color-primary;
    border-radius: 8px;
  }

  &__text {
    font-weight: 600;
    color: #fff;
  }
}

.collapse-btn {
  font-size: 18px;
  color: $text-regular;
  cursor: pointer;
}

.user {
  display: flex;
  gap: 8px;
  align-items: center;
  cursor: pointer;

  &__name {
    font-size: 14px;
    color: $text-regular;
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
