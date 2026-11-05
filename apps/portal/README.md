# @project/portal — 门户网站

Nuxt 4（SSR）· TypeScript。面向搜索引擎与首屏体验的内容站，数据来自 FastAPI 的 `/portal/*` 公开接口。

## 启动

```bash
pnpm --filter @project/portal dev      # http://localhost:3000
pnpm --filter @project/portal build    # 生产构建（Node Server）
pnpm --filter @project/portal generate # 纯静态导出（内容变化不频繁时可用）
```

## 目录

```
app/
├── assets/css/main.css     全局样式与设计变量
├── components/             AppHeader · AppFooter · ArticleCard（自动导入）
├── composables/            usePortalApi.ts（数据获取 + 响应解包）
├── layouts/default.vue     Header + 内容 + Footer
├── pages/                  文件路由
│   ├── index.vue           首页
│   ├── articles/index.vue  资讯列表（分页）
│   ├── articles/[slug].vue 文章详情（动态 SEO meta）
│   └── about.vue
├── app.vue
└── error.vue               404 / 服务异常页
```

## 数据获取

统一走 `usePortalApi.ts`：

```ts
const { data, pending } = await useArticleList({ page: 1, page_size: 6 })
```

`useFetch` 在 SSR 时于服务端发起请求，客户端激活后复用同一份数据，不会重复请求。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `NUXT_PUBLIC_API_BASE` | 后端接口地址，默认 `http://127.0.0.1:8000/api/v1` |

生产部署时建议由 Nginx 把 `/api` 反代到后端，并把 `NUXT_PUBLIC_API_BASE` 设为 `/api/v1`，避免跨域与额外的 DNS 解析。
