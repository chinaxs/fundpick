# 数据获取（portal/composables）

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `usePortalApi.ts` | `useApiBase()` / `useArticleList(params)` / `useArticleDetail(slug)` |
| `useFundApi.ts` | `useFundList` / `useFundFilters` / `useFundDetail` / `useFundMetrics` / `useFundNavs` / `useOverviewStats` / `useReturnDistribution` |
| `useAuth.ts` | 登录态：`ensureSession` / `login` / `register` / `logout` / `openAuth`，令牌存 cookie |

## 请求链路（改之前必读）

```
浏览器  --/api/v1/...-->  Nitro 反向代理  --http://127.0.0.1:8000/api/v1/...-->  FastAPI
SSR     ----------------- 直连后端 -------------------------------------->  FastAPI
```

`useApiBase()` 按运行环境返回不同基址：

- **SSR**：`config.apiBase`（绝对地址，服务端没有同源策略）
- **浏览器**：`config.public.apiBase` = `/api/v1`（同源，由 `routeRules` 代理）

**不要把浏览器基址改成绝对地址。** `localhost`、`127.0.0.1`、`[::1]` 在浏览器里是
不同的源，一旦跨域就必须穷举 CORS 白名单，漏一个组合整页报错，且 `curl` 测不出来
（详见 [ADR-0007](../../../../docs/adr/0007-same-origin-proxy.md)）。

## 登录态为什么用 cookie

`useState` 存用户对象、`useCookie` 存令牌。用 cookie 而非 localStorage 的原因：
SSR 阶段服务端读不到 localStorage，会在首屏渲染成"未登录"，水合后才闪成已登录。
布局里 `await auth.ensureSession()` 让服务端就把用户信息取回来。

`useFundNavs` 的 `period` 支持传 ref：切换区间时 `watch` 触发重新请求，
但 `useAsyncData` 的 key 不含 period，避免每切一次就多一个缓存条目。

## 为什么用 `useAsyncData` 而不是 `useFetch`

`useFetch` 的泛型推导在与 `transform` 组合时不稳定（`data` 会被推断成原始响应类型），
用 `useAsyncData` + 显式泛型更可控，且同样享受 SSR 数据复用（服务端请求一次，客户端接管不再重复请求）。

## 约定
- 所有门户接口调用集中在此，页面不出现 URL。
- 响应解包（`ApiResponse.data`）在 composable 内完成，页面拿到的就是业务数据。
- 列表参数支持 `computed`，翻页时自动重新请求（`watch`）。

## 扩展方式
新增接口：加一个 `useXxx()`，保持"输入参数 → 返回业务数据"的形状。

## 依赖
上游：`@project/shared`、Nuxt runtimeConfig ｜ 下游：`pages`
