/**
 * 与后端 Pydantic 模型一一对应的接口定义。
 * 后端改动 schema 时，这里同步更新（后续可接入 OpenAPI 自动生成）。
 */

/** 统一响应包装：code=0 表示成功 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T | null
  request_id?: string | null
}

/** 分页结果 */
export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** 分页查询参数 */
export interface PageParams {
  page?: number
  page_size?: number
}

// ---------------------------------------------------------------- 用户
export interface User {
  id: number
  username: string
  email: string | null
  full_name: string | null
  avatar_url: string | null
  is_active: boolean
  is_superuser: boolean
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export interface UserCreatePayload {
  username: string
  password: string
  email?: string | null
  full_name?: string | null
  is_superuser?: boolean
}

export interface UserUpdatePayload {
  email?: string | null
  full_name?: string | null
  password?: string
  avatar_url?: string | null
  is_active?: boolean
  is_superuser?: boolean
}

export interface UserQuery extends PageParams {
  keyword?: string
  is_active?: boolean
}

// ---------------------------------------------------------------- 认证
export interface LoginPayload {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface ChangePasswordPayload {
  old_password: string
  new_password: string
}

// ---------------------------------------------------------------- 文章
export type ArticleStatus = 'draft' | 'published' | 'archived'

export interface Article {
  id: number
  title: string
  slug: string | null
  summary: string | null
  content: string | null
  cover_url: string | null
  status: ArticleStatus
  view_count: number
  published_at: string | null
  created_at: string
  updated_at: string
}

export interface ArticleListItem {
  id: number
  title: string
  slug: string
  summary: string | null
  cover_url: string | null
  status: ArticleStatus
  view_count: number
  published_at: string | null
}

export interface ArticleCreatePayload {
  title: string
  slug?: string | null
  summary?: string | null
  content?: string | null
  cover_url?: string | null
  status?: ArticleStatus
}

export type ArticleUpdatePayload = Partial<ArticleCreatePayload>

export interface ArticleQuery extends PageParams {
  status?: ArticleStatus
  keyword?: string
}
