# @project/portal — 门户网站

Nuxt 4（SSR）· TypeScript。面向搜索引擎与首屏体验的基金数据站，数据来自 FastAPI 的 `/portal/*` 公开接口。

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
├── components/             AppHeader · AppFooter · ArticleCard
│                           FundNavChart · TypeBars · ReturnHistogram（自动导入）
├── composables/            usePortalApi.ts · useFundApi.ts（数据获取 + 响应解包）
├── layouts/default.vue     Header + 内容 + Footer
├── pages/                  文件路由
│   ├── index.vue           首页（市场概览 + 榜单）
│   ├── funds/index.vue     基金筛选排行
│   ├── funds/[code].vue    基金详情（净值曲线 + 区间指标）
│   ├── articles/           研报列表与详情
│   └── about.vue
├── app.vue
└── error.vue               404 / 服务异常页
```

## 数据获取

统一走 `composables/`，页面里不出现 URL：

```ts
const { data, pending } = await useFundList({ page: 1, period: '1y', sort_by: 'return' })
```

SSR 时于服务端发起请求，客户端激活后复用同一份 payload，不会重复请求。

## 请求链路与跨域

```
浏览器  --/api/v1/...-->  Nitro 反向代理  -->  http://127.0.0.1:8000/api/v1/...
SSR     -------------- 直连后端 ---------------------------------------->
```

浏览器侧用**同源相对路径**，由 `routeRules` 代理转发，因此不受 CORS 影响；
SSR 侧直连后端绝对地址。基址由 `useApiBase()` 按 `import.meta.server` 切换。

> 不要在前端改用绝对地址，也不要单靠后端 CORS 白名单放行。原因见
> [ADR-0007](../../docs/adr/0007-same-origin-proxy.md)。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `NUXT_API_BASE` | `http://127.0.0.1:8000/api/v1` | 后端真实地址，供 SSR 与反代使用。容器部署填服务名 |
| `NUXT_PUBLIC_API_BASE` | `/api/v1` | 浏览器基址，**必须保持相对路径** |
| `NUXT_PUBLIC_API_DOCS_URL` | `http://127.0.0.1:8000/docs` | 页脚接口文档链接 |
| `NUXT_PUBLIC_ADMIN_URL` | `http://localhost:5174` | 页脚后台入口 |

生产若由 Nginx 统一入口反代 `/api/v1`，可移除 Nitro 代理，但前端基址仍保持 `/api/v1`。
