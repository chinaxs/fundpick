import { STORAGE_KEYS } from '@project/shared'
import { ElMessage } from 'element-plus'
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    icon?: string
    /** 所属菜单分组，缺省则不进菜单 */
    group?: string
    /** 无需登录即可访问 */
    public?: boolean
    /** 不在菜单中显示（如详情、编辑页） */
    hidden?: boolean
    /** 仅超管可见/可访问 */
    superuser?: boolean
  }
}

/** 分组顺序即菜单展示顺序 */
export const MENU_GROUPS = [
  { name: '概览', icon: 'Odometer' },
  { name: '数据', icon: 'DataLine' },
  { name: '内容', icon: 'Document' },
  { name: '用户', icon: 'UserFilled' },
  { name: '系统', icon: 'Setting' },
] as const

/**
 * 业务页面。菜单由这份清单按 `meta.group` 聚合生成，
 * 避免菜单与路由两处维护、改一处忘一处。
 */
export const layoutChildren: RouteRecordRaw[] = [
  {
    path: 'dashboard',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: '仪表盘', icon: 'Odometer', group: '概览' },
  },

  {
    path: 'funds',
    name: 'funds',
    component: () => import('@/views/funds/FundListView.vue'),
    meta: { title: '基金数据', icon: 'TrendCharts', group: '数据' },
  },
  {
    path: 'data-sync',
    name: 'data-sync',
    component: () => import('@/views/data/DataSyncView.vue'),
    meta: { title: '采集监控', icon: 'Refresh', group: '数据' },
  },

  {
    path: 'articles',
    name: 'articles',
    component: () => import('@/views/articles/ArticleListView.vue'),
    meta: { title: '文章管理', icon: 'Document', group: '内容' },
  },
  {
    path: 'articles/new',
    name: 'article-create',
    component: () => import('@/views/articles/ArticleEditView.vue'),
    meta: { title: '新建文章', group: '内容', hidden: true },
  },
  {
    path: 'articles/:id/edit',
    name: 'article-edit',
    component: () => import('@/views/articles/ArticleEditView.vue'),
    meta: { title: '编辑文章', group: '内容', hidden: true },
  },

  {
    path: 'users',
    name: 'users',
    component: () => import('@/views/users/UserListView.vue'),
    meta: { title: '用户管理', icon: 'User', group: '用户' },
  },
  {
    path: 'audit-logs',
    name: 'audit-logs',
    component: () => import('@/views/users/AuditLogView.vue'),
    meta: { title: '操作日志', icon: 'Tickets', group: '用户', superuser: true },
  },

  {
    path: 'settings',
    name: 'settings',
    component: () => import('@/views/system/SettingsView.vue'),
    meta: { title: '个人设置', icon: 'Avatar', group: '系统' },
  },
  {
    path: 'system',
    name: 'system',
    component: () => import('@/views/system/SystemInfoView.vue'),
    meta: { title: '系统信息', icon: 'Monitor', group: '系统', superuser: true },
  },
]

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/DefaultLayout.vue'),
    redirect: { name: 'dashboard' },
    children: layoutChildren,
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在', public: true },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// 全局守卫：未登录跳登录页；超管页面二次校验
router.beforeEach(async (to) => {
  const hasToken = Boolean(localStorage.getItem(STORAGE_KEYS.accessToken))

  if (!to.meta.public && !hasToken) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && hasToken) {
    return { name: 'dashboard' }
  }

  // 菜单已经按角色隐藏，这里防的是直接敲 URL
  if (to.meta.superuser) {
    const authStore = useAuthStore()
    if (!authStore.currentUser) {
      await authStore.fetchProfile().catch(() => null)
    }
    if (!authStore.isSuperuser) {
      ElMessage.warning('该页面仅管理员可访问')
      return { name: 'dashboard' }
    }
  }

  return true
})

router.afterEach((to) => {
  const appTitle = import.meta.env.VITE_APP_TITLE ?? '管理后台'
  document.title = to.meta.title ? `${to.meta.title} · ${appTitle}` : appTitle
})

export default router
