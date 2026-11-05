import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { STORAGE_KEYS } from '@project/shared'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    icon?: string
    /** 无需登录即可访问 */
    public?: boolean
  }
}

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
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '仪表盘', icon: 'Odometer' },
      },
      {
        path: 'funds',
        name: 'funds',
        component: () => import('@/views/funds/FundListView.vue'),
        meta: { title: '基金管理', icon: 'TrendCharts' },
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('@/views/users/UserListView.vue'),
        meta: { title: '用户管理', icon: 'User' },
      },
      {
        path: 'articles',
        name: 'articles',
        component: () => import('@/views/articles/ArticleListView.vue'),
        meta: { title: '文章管理', icon: 'Document' },
      },
    ],
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

// 全局守卫：未登录跳登录页，已登录不再进登录页
router.beforeEach((to) => {
  const hasToken = Boolean(localStorage.getItem(STORAGE_KEYS.accessToken))

  if (!to.meta.public && !hasToken) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && hasToken) {
    return { name: 'dashboard' }
  }
  return true
})

router.afterEach((to) => {
  const appTitle = import.meta.env.VITE_APP_TITLE ?? '管理后台'
  document.title = to.meta.title ? `${to.meta.title} · ${appTitle}` : appTitle
})

export default router
