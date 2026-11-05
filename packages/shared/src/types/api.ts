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

// ---------------------------------------------------------------- 基金
export type FundType = 'stock' | 'hybrid' | 'bond' | 'index' | 'qdii' | 'money' | 'fof' | 'other'

export type RiskLevel = 'low' | 'mid_low' | 'mid' | 'mid_high' | 'high'

export type FundStatus = 'open' | 'suspended' | 'closed'

export type FundPeriod = '1w' | '1m' | '3m' | '6m' | '1y' | '2y' | '3y' | 'ytd' | 'all'

export type FundSortBy = 'return' | 'sharpe' | 'max_drawdown' | 'volatility' | 'scale' | 'nav'

export type SortOrder = 'asc' | 'desc'

/** 列表项：字段与后端 FundListItem 一一对应 */
export interface FundListItem {
  id: number
  code: string
  name: string
  type: FundType
  risk_level: RiskLevel | null
  company_name: string | null
  manager_name: string | null
  /** 单位净值 */
  latest_nav: number | null
  latest_nav_date: string | null
  /** 规模（亿元） */
  scale: number | null
  /** 管理费率（%/年） */
  fee_rate: number | null
  /** 所选区间收益率（%） */
  return_rate: number | null
  /** 最大回撤（%，正数表示回撤幅度） */
  max_drawdown: number | null
  /** 年化波动率（%） */
  volatility: number | null
  sharpe: number | null
  rank: number | null
  total: number | null
}

export interface FundDetail extends FundListItem {
  full_name: string | null
  status: FundStatus
  inception_date: string | null
  custody_fee: number | null
  is_index: boolean
  tracking_index: string | null
  manager_tenure_years: number | null
  manager_scale: number | null
  manager_best_return: number | null
}

export interface FundQuery extends PageParams {
  keyword?: string
  type?: FundType
  risk_level?: RiskLevel
  company_id?: number
  period?: FundPeriod
  sort_by?: FundSortBy
  sort_order?: SortOrder
}

export interface FundMetric {
  period: string
  return_rate: number | null
  annual_return: number | null
  max_drawdown: number | null
  volatility: number | null
  sharpe: number | null
  rank: number | null
  total: number | null
}

export interface NavPoint {
  nav_date: string
  unit_nav: number
  daily_return: number | null
}

export interface FilterOption {
  value: string | number
  label: string
}

export interface FilterOptions {
  types: FilterOption[]
  risk_levels: FilterOption[]
  companies: FilterOption[]
  periods: FilterOption[]
  sort_fields: FilterOption[]
}

// ---------------------------------------------------------------- 统计
export interface TypeStat {
  type: FundType
  label: string
  count: number
  /** 该类型区间平均收益（%） */
  avg_return: number | null
}

export interface OverviewStats {
  total_funds: number
  total_companies: number
  latest_nav_date: string | null
  type_distribution: TypeStat[]
}

export interface DistributionBucket {
  label: string
  count: number
}

export interface ReturnDistribution {
  period: string
  total: number
  buckets: DistributionBucket[]
}
