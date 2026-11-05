# 数据获取（portal/composables）

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `usePortalApi.ts` | `useApiBase()` / `useArticleList(params)` / `useArticleDetail(slug)` |

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
