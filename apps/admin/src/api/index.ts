/** 业务接口定义：按模块拆分，页面只调用这里。
 *
 * 后台接口统一挂在 `/api/v1/admin/**` 下（与门户的 `/portal/**` 分离），
 * 因此所有路径都以 `ADMIN` 开头——不写死前缀，避免将来迁移时漏改。
 */
import type {
  Article,
  ArticleCreatePayload,
  ArticleListItem,
  ArticleQuery,
  ArticleUpdatePayload,
  ChangePasswordPayload,
  LoginPayload,
  PageResult,
  StaffCreatePayload,
  StaffQuery,
  StaffUpdatePayload,
  StaffUser,
  TokenResponse,
  User,
  UserCreatePayload,
  UserQuery,
  UserUpdatePayload,
} from '@project/shared'

import type {
  ArticleVersionItem,
  FeedbackItem,
  FundListItem,
  FundQuery,
  MemberPortfolioSummary,
  MemberSupportSummary,
  PasswordResetLink,
  PasswordResetRequestItem,
} from '@project/shared'

import type {
  AuditLogItem,
  AuditQuery,
  DashboardOverview,
  DataQualityReport,
  EngagementSummary,
  FeedbackQuery,
  FeedbackRow,
  FeedbackUpdatePayload,
  OpsStatus,
  SyncAlert,
  SyncJob,
  SyncSchedule,
  SyncSchedulePayload,
  SyncTriggerPayload,
  SyncStatus,
  SystemInfo,
} from '@/types/admin'

import { api } from './client'

/** 后台接口前缀。门户接口用 `/portal/**`，两边不共用。 */
const ADMIN = '/admin'

/** 后台员工认证（staff_users 表，与门户会员账号彻底分离） */
export const authApi = {
  login: (payload: LoginPayload) => api.post<TokenResponse>(`${ADMIN}/auth/login`, payload),
  me: () => api.get<StaffUser>(`${ADMIN}/auth/me`),
  logout: (refresh_token: string) =>
    api.post<{ message: string }>(`${ADMIN}/auth/logout`, { refresh_token }),
  changePassword: (payload: ChangePasswordPayload) =>
    api.post<{ message: string }>(`${ADMIN}/auth/change-password`, payload),
}

/** 门户会员管理（users 表） */
export const userApi = {
  list: (params: UserQuery) => api.get<PageResult<User>>(`${ADMIN}/users`, params),
  detail: (id: number) => api.get<User>(`${ADMIN}/users/${id}`),
  create: (payload: UserCreatePayload) => api.post<User>(`${ADMIN}/users`, payload),
  update: (id: number, payload: UserUpdatePayload) =>
    api.patch<User>(`${ADMIN}/users/${id}`, payload),
  remove: (id: number) => api.delete<{ id: number }>(`${ADMIN}/users/${id}`),
  batchRemove: (ids: number[]) =>
    api.post<{ affected: number }>(`${ADMIN}/users/batch-delete`, { ids }),
}

/** 后台员工账号管理（staff_users 表，仅超管） */
export const staffApi = {
  list: (params: StaffQuery) => api.get<PageResult<StaffUser>>(`${ADMIN}/staff`, params),
  detail: (id: number) => api.get<StaffUser>(`${ADMIN}/staff/${id}`),
  create: (payload: StaffCreatePayload) => api.post<StaffUser>(`${ADMIN}/staff`, payload),
  update: (id: number, payload: StaffUpdatePayload) =>
    api.patch<StaffUser>(`${ADMIN}/staff/${id}`, payload),
  remove: (id: number) => api.delete<{ id: number }>(`${ADMIN}/staff/${id}`),
  batchRemove: (ids: number[]) =>
    api.post<{ affected: number }>(`${ADMIN}/staff/batch-delete`, { ids }),
}

export const articleApi = {
  list: (params: ArticleQuery) => api.get<PageResult<ArticleListItem>>(`${ADMIN}/articles`, params),
  detail: (id: number) => api.get<Article>(`${ADMIN}/articles/${id}`),
  create: (payload: ArticleCreatePayload) => api.post<Article>(`${ADMIN}/articles`, payload),
  update: (id: number, payload: ArticleUpdatePayload) =>
    api.patch<Article>(`${ADMIN}/articles/${id}`, payload),
  remove: (id: number) => api.delete<{ id: number }>(`${ADMIN}/articles/${id}`),
  batchRemove: (ids: number[]) =>
    api.post<{ affected: number }>(`${ADMIN}/articles/batch-delete`, { ids }),
  batchStatus: (ids: number[], status: ArticleListItem['status']) =>
    api.post<{ affected: number }>(`${ADMIN}/articles/batch-status`, { ids, status }),
  versions: (id: number) => api.get<ArticleVersionItem[]>(`${ADMIN}/articles/${id}/versions`),
  restoreVersion: (id: number, version: number) =>
    api.post<Article>(`${ADMIN}/articles/${id}/versions/${version}/restore`),
}

export const fundApi = {
  list: (params: FundQuery) => api.get<PageResult<FundListItem>>(`${ADMIN}/funds`, params),
  syncStatus: () => api.get<SyncStatus>(`${ADMIN}/funds/sync-status`),
  dataQuality: (params?: { page?: number; page_size?: number; keyword?: string }) =>
    api.get<DataQualityReport>(`${ADMIN}/funds/data-quality`, params),
  triggerSync: (payload: SyncTriggerPayload) => api.post<SyncJob>(`${ADMIN}/funds/sync`, payload),
  syncJobs: (limit = 20) => api.get<SyncJob[]>(`${ADMIN}/funds/sync/jobs`, { limit }),
  syncJob: (id: number) => api.get<SyncJob>(`${ADMIN}/funds/sync/jobs/${id}`),
  cancelSync: (id: number) => api.post<SyncJob>(`${ADMIN}/funds/sync/jobs/${id}/cancel`),
  retrySync: (id: number) => api.post<SyncJob>(`${ADMIN}/funds/sync/jobs/${id}/retry`),
  syncAlerts: (hours = 24) => api.get<SyncAlert[]>(`${ADMIN}/funds/sync/alerts`, { hours }),
  syncSchedules: () => api.get<SyncSchedule[]>(`${ADMIN}/funds/sync/schedules`),
  installRecommendedSchedules: () =>
    api.post<SyncSchedule[]>(`${ADMIN}/funds/sync/schedules/recommended`),
  createSchedule: (payload: SyncSchedulePayload) =>
    api.post<SyncSchedule>(`${ADMIN}/funds/sync/schedules`, payload),
  updateSchedule: (id: number, payload: Partial<SyncSchedulePayload>) =>
    api.patch<SyncSchedule>(`${ADMIN}/funds/sync/schedules/${id}`, payload),
  removeSchedule: (id: number) => api.delete<null>(`${ADMIN}/funds/sync/schedules/${id}`),
}

/** 会员支持：反馈工单、密码重置与只读排查（仅超管） */
export const supportApi = {
  feedback: (params: FeedbackQuery) =>
    api.get<PageResult<FeedbackRow>>(`${ADMIN}/support/feedback`, params),
  updateFeedback: (id: number, payload: FeedbackUpdatePayload) =>
    api.patch<FeedbackItem>(`${ADMIN}/support/feedback/${id}`, payload),
  passwordResets: (params?: { status?: string; limit?: number }) =>
    api.get<PasswordResetRequestItem[]>(`${ADMIN}/support/password-resets`, params),
  createResetLink: (userId: number) =>
    api.post<PasswordResetLink>(`${ADMIN}/support/members/${userId}/reset-link`),
  member: (userId: number) => api.get<MemberSupportSummary>(`${ADMIN}/support/members/${userId}`),
  memberPortfolio: (userId: number, limit = 200) =>
    api.get<MemberPortfolioSummary>(`${ADMIN}/support/members/${userId}/portfolio`, { limit }),
}

/** 运营概览：一次拉全首页所需的聚合数据 */
export const dashboardApi = {
  overview: () => api.get<DashboardOverview>(`${ADMIN}/dashboard`),
  engagement: () => api.get<EngagementSummary>(`${ADMIN}/dashboard/engagement`),
}

/** 操作审计（仅超管） */
export const auditApi = {
  list: (params: AuditQuery) => api.get<PageResult<AuditLogItem>>(`${ADMIN}/audit-logs`, params),
}

/** 系统信息（仅超管） */
export const systemApi = {
  info: () => api.get<SystemInfo>(`${ADMIN}/system/info`),
  health: () => api.get<OpsStatus>(`${ADMIN}/system/health`),
}
