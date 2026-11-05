/**
 * 门户数据获取封装：统一 baseURL 与响应解包。
 *
 * 采用 useAsyncData + $fetch 而不是 useFetch：
 * useFetch 的泛型推导在与 transform 组合时不稳定，显式声明返回类型更可控。
 * SSR 期间请求在服务端发出，客户端接管后复用同一份 payload。
 */
import type { MaybeRef } from 'vue'
import type { ApiResponse, Article, ArticleListItem, PageResult } from '@project/shared'

export function useApiBase() {
  return useRuntimeConfig().public.apiBase
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
