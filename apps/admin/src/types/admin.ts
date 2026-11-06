/** 后台运营视图的类型（仅管理端使用，故不放 shared） */

export interface AuditLogItem {
  id: number
  username: string | null
  action: string
  resource: string
  resource_id: string | null
  method: string
  path: string
  status_code: number
  ip: string | null
  duration_ms: number | null
  detail: string | null
  created_at: string
}

export interface AuditQuery {
  username?: string
  resource?: string
  action?: string
  status_code?: number
  start?: string
  end?: string
  page?: number
  page_size?: number
}

export interface CoverageItem {
  key: string
  label: string
  covered: number
  total: number
  percent: number
}

export interface TypeCount {
  type: string
  label: string
  count: number
  avg_return: number | null
}

export interface RecentUser {
  id: number
  username: string
  email: string | null
  created_at: string
}

export interface DashboardOverview {
  funds_total: number
  companies_total: number
  managers_total: number
  nav_latest_date: string | null
  nav_date_lag_days: number | null
  coverage: CoverageItem[]
  user_total: number
  user_staff: number
  user_new_7d: number
  article_total: number
  article_published: number
  favorite_total: number
  type_distribution: TypeCount[]
  recent_users: RecentUser[]
  recent_audits: AuditLogItem[]
  server_time: string
}

export interface TableStat {
  name: string
  rows: number
  comment: string | null
}

export interface SystemInfo {
  app_name: string
  version: string
  environment: string
  debug: boolean
  python_version: string
  database: string
  started_at: string
  uptime_seconds: number
  tables: TableStat[]
}

export interface SyncStatus {
  fund_total: number
  nav_rows: number
  latest_nav_date: string | null
}
