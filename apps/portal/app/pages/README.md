# 页面（portal/pages）

Nuxt 文件路由，文件名即路径。

## 结构
| 文件 | 路由 | 说明 |
| --- | --- | --- |
| `index.vue` | `/` | 首页：Hero、特性、最新 3 篇 |
| `articles/index.vue` | `/articles` | 资讯列表 + 分页（`?page=`） |
| `articles/[slug].vue` | `/articles/:slug` | 详情：SSR 拉取、Markdown 渲染、动态 SEO meta |
| `about.vue` | `/about` | 关于页（技术栈与目录说明） |

## 约定
- 数据一律通过 `composables/usePortalApi.ts` 获取，不直接 `$fetch`。
- 每页必须设置 `useSeoMeta({ title, description })`，详情页用函数形式（依赖异步数据）。
- 404 用 `throw createError({ statusCode: 404, fatal: true })`，由 `app/error.vue` 渲染。

## 扩展方式
新增页面：建 `.vue` 文件即生成路由；若需出现在导航，改 `components/AppHeader.vue` 的 `navs`。

## 依赖
上游：`composables`、`components`、`@project/shared` ｜ 下游：无
