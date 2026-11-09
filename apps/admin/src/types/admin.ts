/** 后台运营视图的类型（仅管理端使用，故不放 shared） */

import type { FeedbackItem, FeedbackStatus } from '@project/shared'

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
  expected_nav_date: string | null
  nav_lag_trading_days: number | null
  freshness_state: string
  freshness_message: string
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
  expected_nav_date: string | null
  calendar_known: boolean
  nav_lag_trading_days: number | null
  freshness_state: string
  freshness_message: string
  checked_at: string
  current_funds: number | null
  lagging_funds: number | null
  missing_nav_funds: number
  special_funds: number
  scheduler_enabled: boolean
  enabled_schedules: number
  last_data_sync_at: string | null
  auto_reconcile_enabled: boolean
  auto_reconcile_interval_seconds: number
  pending_automatic: number
  last_automatic_check_at: string | null
}

export interface DataQualitySummary {
  total_funds: number
  affected_funds: number
  missing_nav: number
  lagging_nav: number
  missing_return: number
  stale_risk: number
  missing_profile: number
}

export interface DataQualityIssue {
  code: string
  name: string
  fields: string[]
  latest_nav_date: string | null
  nav_age_days: number | null
  risk_nav_date: string | null
  suggested_mode: 'snapshot' | 'risk' | 'detail'
}

export interface DataQualityReport {
  checked_on: string
  nav_stale_after_days: number
  expected_nav_date: string | null
  calendar_known: boolean
  freshness_note: string
  summary: DataQualitySummary
  items: DataQualityIssue[]
  total: number
  page: number
  page_size: number
}

/** 手动同步任务（sync_jobs 表） */
export interface SyncFailureItem {
  item: string
  reason: string
}

export interface SyncJob {
  id: number
  mode: string
  params: string | null
  status:
    'starting' | 'running' | 'partial_success' | 'success' | 'failed' | 'cancelled' | 'timeout'
  triggered_by: string | null
  pid: number | null
  log_file: string | null
  phase: string | null
  total: number
  succeeded: number
  failed: number
  skipped: number
  failures: SyncFailureItem[]
  heartbeat_at: string | null
  cancel_requested: boolean
  timeout_seconds: number
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  message: string | null
  log_tail: string | null
}

export interface SyncSchedule {
  id: number
  mode: string
  hour: number
  minute: number
  weekdays: string
  enabled: boolean
  last_run_on: string | null
  last_job_id: number | null
}

export interface SyncSchedulePayload {
  mode: string
  hour: number
  minute: number
  weekdays: string
  enabled: boolean
}

export interface SyncAlert {
  level: 'error' | 'warning'
  job_id: number | null
  mode: string | null
  title: string
  detail: string
  at: string
}

export interface SyncTriggerPayload {
  mode: string
  limit?: number | null
  codes?: string | null
  force?: boolean
}

export const SYNC_MODE_OPTIONS: { value: string; label: string; hint: string }[] = [
  { value: 'quick', label: '基础数据 / 最新净值', hint: '约 1 分钟，刷新列表页净值与区间收益' },
  {
    value: 'snapshot',
    label: '净值与区间收益',
    hint: '更新全市场净值快照，可填写代码限定范围；历史曲线和风险由持仓与关注更新任务补齐',
  },
  {
    value: 'tracked',
    label: '持仓与关注数据',
    hint: '更新持仓、关注及待入账基金的历史净值和风险指标',
  },
  { value: 'risk', label: '风险指标', hint: '逐只请求，耗时较长，建议配合 limit 分批' },
  { value: 'sector', label: '主题板块推导', hint: '本地规则推导，秒级完成' },
  { value: 'risk-level', label: '风险等级推导', hint: '本地规则推导，秒级完成' },
  { value: 'navs', label: '历史净值序列', hint: '按 limit 批量拉取' },
  { value: 'detail', label: '基金档案与费率', hint: '逐只请求，耗时较长' },
  { value: 'holdings', label: '季度重仓股', hint: '逐只请求，耗时较长' },
  { value: 'scale', label: '基金规模', hint: '批量更新规模' },
  {
    value: 'news',
    label: '资讯快讯',
    hint: '抓取政策 / 市场快讯，生成草稿待审核（几秒完成）',
  },
  { value: 'all', label: '全量同步', hint: '包含所有模式，耗时非常长，谨慎使用' },
]

/** 会员支持：反馈工单（带会员标识）与筛选条件 */
export type FeedbackRow = FeedbackItem & { username: string | null; email: string | null }

export interface FeedbackQuery {
  page?: number
  page_size?: number
  status?: string
  category?: string
  keyword?: string
}

export interface FeedbackUpdatePayload {
  status?: FeedbackStatus
  reply?: string | null
}

/** 运营效果指标（已排除测试帐号，比例由前端计算） */
export interface EngagementPoint {
  day: string
  users: number
}

export interface EngagementSummary {
  total_users: number
  new_7d: number
  active_7d: number
  active_30d: number
  returning_7d: number
  retention_cohort: number
  retention_7d: number
  users_with_favorite: number
  users_with_transaction: number
  daily_active: EngagementPoint[]
  excluded_note: string
  definitions: string
}

/** 运行健康度：日志、备份与告警 */
export interface OpsLogFile {
  name: string
  size_bytes: number
  modified_at: string
}

export interface OpsBackup {
  name: string
  size_bytes: number
  created_at: string
  total_backups: number
  restore_drill_at: string | null
  restore_drill_ok: boolean | null
}

export interface OpsAlert {
  level: 'error' | 'warning'
  category: 'data' | 'sync' | 'backup' | 'logs'
  title: string
  detail: string
}

export interface OpsStatus {
  logs: OpsLogFile[]
  backup: OpsBackup | null
  alerts: OpsAlert[]
  checked_at: string
}
