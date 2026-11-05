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

/** 基金类型字典（前端展示用，与后端 TYPE_LABELS 保持一致） */
export const FUND_TYPE_MAP = {
  stock: '股票型',
  hybrid: '混合型',
  bond: '债券型',
  index: '指数型',
  qdii: 'QDII',
  money: '货币型',
  fof: 'FOF',
  other: '其他',
} as const

/** 风险等级字典 */
export const RISK_LEVEL_MAP = {
  low: '低风险',
  mid_low: '中低风险',
  mid: '中风险',
  mid_high: '中高风险',
  high: '高风险',
} as const

/** 区间字典 */
export const FUND_PERIOD_MAP = {
  '1w': '近1周',
  '1m': '近1月',
  '3m': '近3月',
  '6m': '近6月',
  '1y': '近1年',
  '2y': '近2年',
  '3y': '近3年',
  ytd: '今年来',
  all: '成立来',
} as const

/** 排序字段字典 */
export const FUND_SORT_MAP = {
  return: '区间收益',
  sharpe: '夏普比率',
  max_drawdown: '最大回撤',
  volatility: '年化波动率',
  scale: '规模',
  nav: '最新净值',
} as const
