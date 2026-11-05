/** 前后端共享常量 */

/** 后端 API 版本前缀 */
export const API_PREFIX = '/api/v1'

/** localStorage 键名，统一管理避免拼写漂移 */
export const STORAGE_KEYS = {
  accessToken: 'study_access_token',
  refreshToken: 'study_refresh_token',
} as const

/** 默认分页大小 */
export const DEFAULT_PAGE_SIZE = 20

export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100] as const

/** 文章状态字典（后台下拉框 / 标签颜色共用） */
export const ARTICLE_STATUS_MAP = {
  draft: { label: '草稿', type: 'info' },
  published: { label: '已发布', type: 'success' },
  archived: { label: '已归档', type: 'warning' },
} as const

/** 业务码：与后端 AppException.code 对齐 */
export const BIZ_CODE = {
  ok: 0,
  unauthorized: 40100,
  forbidden: 40300,
  notFound: 40400,
  conflict: 40900,
  validation: 42200,
  server: 50000,
} as const
