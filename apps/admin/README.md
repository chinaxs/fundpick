# @project/admin — 后台管理系统

Vue 3 + Vite + TypeScript + Element Plus + Pinia + Vue Router。

## 启动

```bash
pnpm --filter @project/admin dev      # http://localhost:5174
pnpm --filter @project/admin build    # 产物在 dist/
```

开发时 `/api` 由 Vite 代理到 `VITE_PROXY_TARGET`（默认 `http://127.0.0.1:8000`），因此无需处理跨域。

## 目录

```
src/
├── api/           client.ts（axios 实例 + 拦截器）· index.ts（按模块的接口函数）
├── layouts/       DefaultLayout.vue（侧边栏 + 顶栏 + 面包屑）
├── router/        路由表 + 登录守卫
├── stores/        auth（登录态）、app（UI 状态）
├── styles/        variables.scss（设计变量）、index.scss（全局样式）
└── views/         LoginView / DashboardView / users / articles / NotFoundView
```

## 约定

- 页面只通过 `src/api` 调用接口，不直接使用 axios。
- 接口返回已由 `client.ts` 解包，拿到的就是业务数据；失败会自动弹提示。
- 新页面注册到 `router/index.ts`，并同步 `layouts/DefaultLayout.vue` 的菜单数组。
- 样式用 `<style scoped lang="scss">`，颜色 / 间距取 `variables.scss` 中的变量。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `VITE_API_BASE_URL` | 接口前缀，默认 `/api/v1` |
| `VITE_PROXY_TARGET` | 开发代理目标 |
| `VITE_APP_TITLE` | 页面标题后缀 |
