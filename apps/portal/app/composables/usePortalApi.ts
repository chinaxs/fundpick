/**
 * 门户数据获取封装：统一 baseURL 与响应解包。
 *
 * 采用 useAsyncData + $fetch 而不是 useFetch：
 * useFetch 的泛型推导在与 transform 组合时不稳定，显式声明返回类型更可控。
 * SSR 期间请求在服务端发出，客户端接管后复用同一份 payload。
 */
import type { MaybeRef } from 'vue'
import type { ApiResponse, Article, ArticleListItem, PageResult } from '@project/shared'

/**
 * 请求基址。
 *
 * - SSR：Node 直连后端绝对地址（服务端没有同源策略）。
 * - 浏览器：走同源的 `/api/v1`，由 Nitro 反向代理转发。
 *
 * 早期版本让浏览器也直连 `http://127.0.0.1:8000`，导致 CORS 白名单必须
 * 精确枚举每一个 `协议+主机+端口` 组合——`localhost`、`127.0.0.1`、`[::1]`
 * 在浏览器里是三个不同的源，漏配任何一个就整页报错。改走代理后不再依赖白名单。
 */
export function useApiBase() {
  const config = useRuntimeConfig()
  return import.meta.server ? config.apiBase : config.public.apiBase
}

interface ArticleListParams {
  page?: number
  page_size?: number
  keyword?: string
}

/** 已发布文章列表（params 可为 ref/computed，变化时自动重新请求） */
export function useArticleList(params: MaybeRef<ArticleListParams> = {}) {
  return useAsyncData<PageResult<ArticleListItem>>(
    'portal-articles',
    async () => {
      const res = await $fetch<ApiResponse<PageResult<ArticleListItem>>>('/portal/articles', {
        baseURL: useApiBase(),
        query: unref(params),
      })
      return res.data ?? { items: [], total: 0, page: 1, page_size: 10 }
    },
    { watch: [() => unref(params)] },
  )
}

/** 文章详情（按 slug） */
export function useArticleDetail(slug: string) {
  return useAsyncData<Article | null>(`portal-article-${slug}`, async () => {
    const res = await $fetch<ApiResponse<Article>>(`/portal/articles/${slug}`, {
      baseURL: useApiBase(),
    })
    return res.data
  })
}
