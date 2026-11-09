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

// ---------------------------------------------------------------- 门户会员（users 表）
/** 官网注册的会员。后台员工见 StaffUser（staff_users 表），两边彻底分离 */
export interface User {
  id: number
  username: string
  email: string | null
  full_name: string | null
  avatar_url: string | null
  is_active: boolean
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export interface UserCreatePayload {
  username: string
  password: string
  email?: string | null
  full_name?: string | null
}

export interface UserUpdatePayload {
  email?: string | null
  full_name?: string | null
  password?: string
  avatar_url?: string | null
  is_active?: boolean
}

export interface UserQuery extends PageParams {
  keyword?: string
  is_active?: boolean
}

// ---------------------------------------------------------------- 后台员工（staff_users 表）
/** 可登录管理后台的员工账号 */
export interface StaffUser {
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

export interface StaffCreatePayload {
  username: string
  password: string
  email?: string | null
  full_name?: string | null
  is_superuser?: boolean
}

export interface StaffUpdatePayload {
  email?: string | null
  full_name?: string | null
  password?: string
  avatar_url?: string | null
  is_active?: boolean
  is_superuser?: boolean
}

export interface StaffQuery extends PageParams {
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
/** 资讯分类：与后端 ARTICLE_CATEGORIES 一致 */
export type ArticleCategory = 'policy' | 'market' | 'company' | 'other'

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
  category: ArticleCategory
  source: string | null
  source_name: string | null
  source_url: string | null
  origin: 'manual' | 'sync'
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
  category: ArticleCategory
  source: string | null
  source_name: string | null
  source_url: string | null
  origin: 'manual' | 'sync'
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

export type FundSector =
  | 'ai'
  | 'semiconductor'
  | 'new_energy'
  | 'military'
  | 'medicine'
  | 'consumer'
  | 'agriculture'
  | 'media'
  | 'internet'
  | 'finance'
  | 'real_estate'
  | 'resources'
  | 'environment'
  | 'infrastructure'
  | 'manufacturing'
  | 'tech'
  | 'broad_index'

export type RiskLevel = 'low' | 'mid_low' | 'mid' | 'mid_high' | 'high'

export type FundStatus = 'open' | 'suspended' | 'closed'

export type FundPeriod = '1w' | '1m' | '3m' | '6m' | '1y' | '2y' | '3y' | 'ytd' | 'all'

/** 净值曲线的时间区间（与排行口径的 FundPeriod 区分） */
export type NavRange = '1m' | '3m' | '6m' | '1y' | '3y' | 'all'

export type FundSortBy = 'return' | 'sharpe' | 'max_drawdown' | 'volatility' | 'scale' | 'nav'

export type SortOrder = 'asc' | 'desc'

/** 列表项：字段与后端 FundListItem 一一对应 */
export interface FundListItem {
  id: number
  code: string
  name: string
  type: FundType
  risk_level: RiskLevel | null
  /** 主题板块 key；null 表示无明显主题（综合） */
  sector: FundSector | null
  company_name: string | null
  manager_name: string | null
  /** 份额类别（A/C 等）；非份额基金为 null */
  share_class?: string | null
  /** 去掉份额类别的基础名称 */
  base_name?: string | null
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
  sector?: FundSector
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
  risk_nav_date: string | null
  risk_source: string | null
  risk_coverage: number
  risk_stale: boolean
  rank: number | null
  total: number | null
}

export interface NavPoint {
  nav_date: string
  unit_nav: number
  daily_return: number | null
}

export interface FundHoldingItem {
  quarter: string
  stock_code: string
  stock_name: string | null
  rank: number | null
  ratio: number | null
  shares: number | null
  market_value: number | null
}

export interface FundHoldingsResult {
  quarters: string[]
  quarter: string | null
  items: FundHoldingItem[]
  total_ratio: number | null
}

export interface FilterOption {
  value: string | number
  label: string
}

export interface SectorOption extends FilterOption {
  count: number
}

export interface FilterOptions {
  types: FilterOption[]
  risk_levels: FilterOption[]
  sectors: SectorOption[]
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

// ---------------------------------------------------------------- 市场指数（大盘）
/** 交易状态：未开盘 / 交易中 / 午间休市 / 已收盘 */
export type MarketStatus = 'pre_open' | 'trading' | 'lunch_break' | 'closed'

/** 单个指数快照。点位与涨跌为数据源原值，涨跌幅单位是 %，成交额单位是元 */
export interface IndexQuote {
  code: string
  name: string
  group: string
  price: number | null
  change: number | null
  change_pct: number | null
  open: number | null
  high: number | null
  low: number | null
  prev_close: number | null
  amplitude: number | null
  volume: number | null
  amount: number | null
}

export interface MarketIndicesData {
  items: IndexQuote[]
  market_status: MarketStatus
  status_label: string
  /** 行情所属交易日（收盘后仍显示当天收盘数据） */
  trade_date: string | null
  /** 服务端本次响应的时间 */
  as_of: string
  /** 最近一次成功抓取的时间；降级时可能是几分钟前 */
  fetched_at?: string | null
  /** 原始行情时间；上游快照没有时间戳时为 null，不用抓取时间替代 */
  data_as_of?: string | null
  /** 距上游数据取得时间过去了多少秒 */
  cache_age_seconds?: number | null
  /** true 表示上游失败、展示的是旧缓存 */
  degraded?: boolean
  degraded_reason?: string | null
  /** 交易日历是否覆盖当前年份；false 表示状态按星期估算 */
  calendar_known?: boolean
  source: string
  /** 轮询兜底时的建议间隔（秒） */
  refresh_seconds: number
  /** SSE 推送间隔（秒），也是心跳间隔 */
  push_seconds: number
}

/** 分时点：一个交易日 241 个（09:30–11:30、13:00–15:00） */
export interface IndexMinutePoint {
  /** HH:MM */
  time: string
  price: number
  /** 当日累计均价 */
  avg_price: number | null
  volume: number | null
  amount: number | null
}

export interface IndexCandlePoint {
  /** YYYY-MM-DD */
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  volume: number | null
  amount: number | null
}

export interface IndexCandlesData {
  code: string
  name: string
  /** 返回的交易日数量（不足则全部返回） */
  days: number
  points: IndexCandlePoint[]
  as_of: string
  fetched_at?: string | null
  data_as_of?: string | null
  cache_age_seconds?: number | null
  degraded?: boolean
  degraded_reason?: string | null
  /** 交易日历是否覆盖当前年份；false 表示状态按星期估算 */
  calendar_known?: boolean
  source: string
}

export interface IndexIntradayData {
  code: string
  name: string
  /** 昨收：分时图基准线，也是每个点涨跌幅的分母 */
  prev_close: number | null
  points: IndexMinutePoint[]
  trade_date: string | null
  market_status: MarketStatus
  status_label: string
  as_of: string
  fetched_at?: string | null
  data_as_of?: string | null
  cache_age_seconds?: number | null
  degraded?: boolean
  degraded_reason?: string | null
  /** 交易日历是否覆盖当前年份；false 表示状态按星期估算 */
  calendar_known?: boolean
  source: string
  refresh_seconds: number
}

export interface IndexTrendPoint {
  trade_date: string
  close: number
}

export interface IndexTrend {
  code: string
  name: string
  points: IndexTrendPoint[]
  change_pct: number | null
}

export interface IndexTrendsData {
  days: number
  items: IndexTrend[]
  as_of: string
}

// ---------------------------------------------------------------- 门户会员
/** 门户登录用户。与后台 User 分开：不含 is_staff / is_superuser 等内部字段 */
export interface PortalUser {
  id: number
  username: string
  email: string | null
  full_name: string | null
  avatar_url: string | null
  created_at: string
  updated_at: string | null
  last_login_at: string | null
}

/** 登录/注册返回的令牌对 */
export interface TokenBundle {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

// ---------------------------------------------------------------- 会员中心
/** 个人中心可修改的字段（用户名、状态、密码都不在此列） */
export interface ProfileUpdatePayload {
  email?: string | null
  full_name?: string | null
  avatar_url?: string | null
}

export interface DashboardSummary {
  total_funds: number
  avg_return: number | null
  positive_ratio: number | null
  avg_sharpe: number | null
  best_return: number | null
  added_last_7_days: number
  metric_coverage: number
  latest_nav_date: string | null
}

export interface DashboardDistributionItem {
  key: string
  label: string
  count: number
  avg_return: number | null
}

export interface DashboardFundItem {
  code: string
  name: string
  type: string
  sector: string | null
  risk_level: string | null
  return_rate: number | null
  max_drawdown: number | null
  sharpe: number | null
  latest_nav: number | null
  favored_at: string | null
}

export interface PositionItem {
  id: number
  code: string
  name: string
  type: string
  sector: string | null
  /** 买入金额（成本，元） */
  amount: number
  /** 买入日期对应的单位净值（系统自动取，无需用户手填） */
  cost_nav: number
  /** 该净值对应的交易日 */
  cost_nav_date: string | null
  /** history=历史净值；latest=回退到最新净值 */
  nav_source: 'history' | 'latest'
  bought_at: string
  note: string | null
  /** 份额 = 金额 / 买入净值，由服务端计算 */
  shares: number
  latest_nav: number | null
  latest_nav_date: string | null
  market_value: number | null
  profit: number | null
  profit_rate: number | null
  created_at: string | null
}

export interface PositionSummary {
  count: number
  total_amount: number
  /** 仅全部持仓可估值时返回总市值与收益，否则为 null。 */
  total_market_value: number | null
  total_profit: number | null
  profit_rate: number | null
  valued_count: number
}

/** 新增模拟持仓：只录金额与日期，净值/份额由服务端算 */
export interface PositionCreatePayload {
  code: string
  amount: number
  bought_at?: string
  note?: string | null
}

export interface PositionUpdatePayload {
  amount?: number
  bought_at?: string
  note?: string | null
}

export interface PositionListData {
  items: PositionItem[]
  summary: PositionSummary
}

/** 工作台聚合数据：一次请求带齐统计、分布与榜单 */
export interface DashboardData {
  portfolio_summary?: PortfolioSummary | null
  period: string
  summary: DashboardSummary
  type_distribution: DashboardDistributionItem[]
  risk_distribution: DashboardDistributionItem[]
  sector_distribution: DashboardDistributionItem[]
  return_buckets: DashboardDistributionItem[]
  top_funds: DashboardFundItem[]
  recent_funds: DashboardFundItem[]
  /** 模拟持仓概览（明细在 /me/positions） */
  position_summary: PositionSummary
}

// ---------------------------------------------------------------- 已确认模拟交易
export interface TradeInput {
  record_source?: 'calculated' | 'receipt' | 'estimated'
  submitted_at?: string
  settled_on?: string
  platform?: string
  receipt_ref?: string
  pricing_rule?: 'cn_open' | 'platform'
  date_reason?: string
  confirmed_shares?: string
  received_amount?: string
  application_id?: number
  code: string
  kind: 'buy' | 'sell'
  confirmed_on: string
  nav_mode: 'official' | 'manual'
  nav?: number | string
  amount?: number | string
  shares?: number | string
  fee: number | string
  note?: string | null
  legacy_position_id?: number
}
export interface TradeEffect {
  code: string
  name: string
  kind: 'buy' | 'sell'
  confirmed_on: string
  nav: number
  nav_source: string
  amount: number
  fee: number
  shares: number
  cash_amount: number
  realized_profit: number
  remaining_shares: number
  remaining_cost: number
  note: string | null
}
export interface TradePreview extends TradeEffect {
  preview_hash: string
  warnings: string[]
}
export interface TradeRead extends TradeEffect {
  calculation_basis: Record<string, unknown> | null
  submitted_at: string | null
  settled_on: string | null
  platform: string | null
  receipt_ref: string | null
  record_source: 'calculated' | 'receipt' | 'estimated'
  pricing_rule: string | null
  date_reason: string | null
  application_id: number | null

  id: number
  status: 'confirmed' | 'voided'
  can_void: boolean
  legacy_position_id: number | null
  created_at: string | null
  voided_at: string | null
  void_reason: string | null
}
export interface HoldingRead {
  estimated_count: number
  code: string
  name: string
  shares: number
  remaining_cost: number
  average_cost: number | null
  latest_nav: number | null
  latest_nav_date: string | null
  market_value: number | null
  holding_profit: number | null
  /** 已实现收益：卖出盈亏 + 现金分红 */
  realized_profit: number
  /** 其中现金分红部分，便于与已实现买卖收益区分 */
  dividends?: number
  total_profit: number | null
  total_buy_amount: number
  total_sell_amount: number
  fees: number
  last_confirmed_on: string
}
export interface PortfolioSummary extends PositionSummary {
  estimated_count: number
  calculated_count: number
  pending_count: number
  realized_profit: number
  total_dividends?: number
  total_return: number | null
  total_buy_amount: number
  total_sell_amount: number
  fees: number
  transaction_count: number
  legacy_count: number
}
export interface PortfolioRead {
  holdings: HoldingRead[]
  summary: PortfolioSummary
  legacy_positions: PositionItem[]
}
export interface TradeSeed {
  submitted_at?: string
  platform?: string
  pricing_rule?: 'cn_open' | 'platform'
  application_id?: number
  requested_shares?: string

  code?: string
  name?: string
  kind: 'buy' | 'sell'
  available_shares?: number
  confirmed_on?: string
  nav?: number
  amount?: number
  legacy_position_id?: number
}

export interface TradeTiming {
  pricing_rule: 'cn_open' | 'platform'
  submitted_at: string
  expected_nav_on: string | null
  official_nav: string | null
  calendar_source: string | null
  message: string
}
export interface ApplicationRead {
  requires_review: boolean
  automatic_processing: boolean
  processing_message: string | null
  id: number
  code: string
  name: string
  kind: 'buy' | 'sell'
  platform: string
  submitted_at: string
  expected_nav_on: string | null
  pricing_rule: 'cn_open' | 'platform'
  amount: string | null
  shares: string | null
  status: 'pending' | 'recorded' | 'cancelled'
  note: string | null
}

export interface AutoTradeRead {
  status: 'recorded' | 'pending'
  transaction: TradeRead | null
  application: ApplicationRead | null
  message: string
}

export interface TradeHistoryQuery {
  page: number
  page_size: number
  keyword?: string
  kind?: 'buy' | 'sell'
  status?: 'pending' | 'confirmed' | 'cancelled' | 'voided'
  start?: string
  end?: string
}
export interface TradeHistoryItem {
  record_type: 'transaction' | 'application'
  id: number
  code: string
  name: string
  kind: 'buy' | 'sell'
  status: 'pending' | 'confirmed' | 'cancelled' | 'voided'
  submitted_at: string | null
  created_at: string | null
  confirmed_on: string | null
  expected_nav_on: string | null
  settled_on: string | null
  platform: string | null
  amount: number | null
  shares: number | null
  nav: number | null
  nav_source: string | null
  fee: number | null
  cash_amount: number | null
  realized_profit: number | null
  record_source: string | null
  receipt_ref: string | null
  calculation_basis: Record<string, unknown> | null
  void_reason: string | null
  note: string | null
  can_void: boolean
  can_cancel: boolean
  can_delete: boolean
  requires_review: boolean
  processing_message: string | null
}

// ---------------------------------------------------------------- 会员支持

export type FeedbackCategory = 'account' | 'data' | 'function' | 'bug' | 'other'
export type FeedbackStatus = 'open' | 'processing' | 'resolved' | 'closed'

export interface FeedbackItem {
  id: number
  user_id: number
  category: FeedbackCategory
  title: string
  content: string
  contact: string | null
  page_url: string | null
  status: FeedbackStatus
  reply: string | null
  handled_by: string | null
  handled_at: string | null
  created_at: string
}

export interface FeedbackCreatePayload {
  category: FeedbackCategory
  title: string
  content: string
  contact?: string | null
  page_url?: string | null
}

export interface MemberSupportSummary {
  id: number
  username: string
  email: string | null
  full_name: string | null
  is_active: boolean
  created_at: string
  last_login_at: string | null
  favorite_count: number
  transaction_count: number
  position_count: number
  open_feedback: number
  pending_reset: number
}

export interface MemberPortfolioItem {
  id: number
  fund_code: string
  fund_name: string
  kind: string
  status: string
  confirmed_on: string
  submitted_at: string | null
  shares: number
  amount: number
  fee: number
  nav: number
  record_source: string
  platform: string | null
  voided_at: string | null
}

export interface MemberPositionItem {
  fund_code: string
  fund_name: string
  shares: number
  cost: number
  market_value: number | null
  updated_at: string | null
}

export interface MemberPortfolioSummary {
  user_id: number
  items: MemberPortfolioItem[]
  positions: MemberPositionItem[]
  total: number
  truncated: boolean
  note: string
}

export interface PasswordResetLink {
  user_id: number
  username: string
  token: string
  expires_at: string
  path: string
}

export interface PasswordResetRequestItem {
  id: number
  user_id: number
  username: string | null
  email: string | null
  requested_ip: string | null
  created_at: string
  used_at: string | null
  expires_at: string | null
  issued_by: string | null
  pending: boolean
}

/** 文章历史版本（后台） */
export interface ArticleVersionItem {
  id: number
  article_id: number
  version: number
  title: string
  summary: string | null
  content: string | null
  category: string
  source_name: string | null
  source_url: string | null
  status: string
  edited_by: string | null
  created_at: string
}

// ---------------------------------------------------------------- 基金对比

export interface ComparePeriod {
  period: string
  label: string
  return_rate: number | null
  max_drawdown: number | null
  sharpe: number | null
  volatility: number | null
  risk_nav_date: string | null
  /** false 表示上游没有该区间的风险数据，不代表 0 */
  available: boolean
}

export interface FundCompareItem {
  code: string
  name: string
  share_class: string | null
  base_name: string | null
  type: FundType
  type_label: string
  risk_level: RiskLevel | null
  risk_label: string | null
  company_name: string | null
  manager_name: string | null
  latest_nav: number | null
  latest_nav_date: string | null
  scale: number | null
  fee_rate: number | null
  custody_fee: number | null
  inception_date: string | null
  periods: ComparePeriod[]
}

export interface FundCompareResult {
  items: FundCompareItem[]
  periods: string[]
  note: string
}
