<script setup lang="ts">
import { ElMessageBox } from 'element-plus'
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { MENU_GROUPS, layoutChildren } from '@/router'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const authStore = useAuthStore()

interface MenuItem {
  name: string
  title: string
  icon: string
}

interface MenuGroup {
  name: string
  icon: string
  children: MenuItem[]
}

/** 菜单由路由表生成：新增页面只需在 router 里加一条，菜单自动出现 */
const groups = computed<MenuGroup[]>(() => {
  const items = layoutChildren
    .filter((r) => r.meta?.group && !r.meta.hidden)
    .filter((r) => !r.meta?.superuser || authStore.isSuperuser)
    .map((r) => ({
      name: String(r.name),
      title: r.meta?.title ?? String(r.name),
      icon: r.meta?.icon ?? 'Menu',
    }))

  return MENU_GROUPS.map((group) => ({
    name: group.name,
    icon: group.icon,
    children: items.filter((item) => {
      const record = layoutChildren.find((r) => r.name === item.name)
      return record?.meta?.group === group.name
    }),
  })).filter((group) => group.children.length > 0)
})

const activeMenu = computed(() => String(route.name ?? ''))

/** 只有一个子项的分组不套二级菜单，直接用子项本身 */
const flatGroups = computed(() => groups.value.filter((g) => g.children.length === 1))
const nestedGroups = computed(() => groups.value.filter((g) => g.children.length > 1))

/** 当前分组默认展开，避免进页面后还要手动点开 */
const defaultOpeneds = computed(() => {
  const group = groups.value.find((g) =>
    g.children.some((child) => child.name === activeMenu.value),
  )
  return group && group.children.length > 1 ? [group.name] : []
})

const breadcrumbs = computed(() => {
  const items: { title: string }[] = [{ title: '首页' }]
  const groupName = route.meta.group as string | undefined
  const nested = nestedGroups.value.some((g) => g.name === groupName)
  if (nested && groupName) items.push({ title: groupName })
  if (route.meta.title) items.push({ title: route.meta.title })
  return items
})

onMounted(() => {
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
        <BrandMark :size="30" class="logo__mark" />
        <span v-show="!appStore.sidebarCollapsed" class="logo__text">拾贝管理</span>
      </div>

      <el-scrollbar class="layout__scroll">
        <el-menu
          :default-active="activeMenu"
          :default-openeds="defaultOpeneds"
          :collapse="appStore.sidebarCollapsed"
          :collapse-transition="false"
          unique-opened
          router
          class="layout__menu"
        >
          <!-- 单页分组：直接是菜单项 -->
          <el-menu-item
            v-for="group in flatGroups"
            :key="group.children[0]!.name"
            :index="group.children[0]!.name"
          >
            <el-icon><component :is="group.children[0]!.icon" /></el-icon>
            <template #title>{{ group.children[0]!.title }}</template>
          </el-menu-item>

          <!-- 多页分组：一级可折叠 -->
          <el-sub-menu v-for="group in nestedGroups" :key="group.name" :index="group.name">
            <template #title>
              <el-icon><component :is="group.icon" /></el-icon>
              <span>{{ group.name }}</span>
            </template>
            <el-menu-item v-for="item in group.children" :key="item.name" :index="item.name">
              <el-icon><component :is="item.icon" /></el-icon>
              <template #title>{{ item.title }}</template>
            </el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-scrollbar>

      <div v-show="!appStore.sidebarCollapsed" class="aside-foot">
        <span class="aside-foot__dot" />
        数据 T+1 · v1.0
      </div>
    </el-aside>

    <el-container>
      <el-header class="layout__header">
        <div class="layout__header-left">
          <el-icon class="collapse-btn" @click="appStore.toggleSidebar()">
            <Fold v-if="!appStore.sidebarCollapsed" />
            <Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item v-for="(item, index) in breadcrumbs" :key="index">
              {{ item.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="layout__header-right">
          <a class="doc-link" href="/docs/admin" target="_blank" rel="noreferrer">
            <el-icon><Document /></el-icon>
            <span>接口文档</span>
          </a>

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
                <el-dropdown-item divided @click="router.push({ name: 'settings' })">
                  个人设置
                </el-dropdown-item>
                <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
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

  &__scroll {
    flex: 1;
    min-height: 0;
  }

  &__menu {
    border-right: none;
    background: transparent;

    :deep(.el-menu-item),
    :deep(.el-sub-menu__title) {
      color: #cbd5e0;

      &:hover {
        color: #fff;
        background: rgb(255 255 255 / 8%);
      }
    }

    :deep(.el-menu-item.is-active) {
      color: #fff;
      background: $color-primary;
    }

    :deep(.el-sub-menu.is-active > .el-sub-menu__title) {
      color: #fff;
    }

    :deep(.el-menu) {
      background: rgb(0 0 0 / 18%);
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

  &__header-right {
    display: flex;
    gap: 20px;
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
    flex: none;
  }

  &__text {
    font-weight: 600;
    color: #fff;
  }
}

.aside-foot {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 14px 18px;
  font-size: 11px;
  color: #64748b;
  border-top: 1px solid rgb(255 255 255 / 6%);

  &__dot {
    width: 6px;
    height: 6px;
    background: #22c55e;
    border-radius: 50%;
  }
}

.collapse-btn {
  font-size: 18px;
  color: $text-regular;
  cursor: pointer;
}

.doc-link {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 13px;
  color: $text-secondary;
  transition: color 0.15s ease;

  &:hover {
    color: $color-primary;
  }
}

.user {
  display: flex;
  gap: 8px;
  align-items: center;
  cursor: pointer;

  &__name {
    font-size: 14px;
    color: $text-primary;
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
