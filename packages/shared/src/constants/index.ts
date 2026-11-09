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

/**
 * 主题板块字典（与后端 app/fund_sectors.py 保持一致）。
 * 板块由基金名称/跟踪指数推导，NULL 表示无明显主题（综合）。
 */
export const FUND_SECTOR_MAP = {
  ai: '人工智能',
  semiconductor: '半导体',
  new_energy: '新能源',
  military: '军工',
  medicine: '医药生物',
  consumer: '消费',
  agriculture: '农业',
  media: '传媒游戏',
  internet: '互联网',
  finance: '金融',
  real_estate: '地产',
  resources: '资源周期',
  environment: '环保',
  infrastructure: '基建',
  manufacturing: '高端制造',
  tech: '科技TMT',
  broad_index: '宽基指数',
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

/** 净值曲线区间字典 */
export const NAV_RANGE_MAP = {
  '1m': '近1月',
  '3m': '近3月',
  '6m': '近6月',
  '1y': '近1年',
  '3y': '近3年',
  all: '成立来',
} as const

/** 净值曲线区间的展示顺序 */
export const NAV_RANGE_ORDER = ['1m', '3m', '6m', '1y', '3y', 'all'] as const

/** 资讯分类，后端 category 字段的展示文案（顺序即筛选栏顺序） */
export const ARTICLE_CATEGORY_MAP: Record<string, { label: string }> = {
  policy: { label: '政策' },
  market: { label: '市场' },
  company: { label: '公司' },
  other: { label: '其他' },
}

/** 反馈分类与处理状态的展示文案 */
export const FEEDBACK_CATEGORY_MAP: Record<string, string> = {
  account: '账号',
  data: '数据',
  function: '功能建议',
  bug: '故障',
  other: '其他',
}

export const FEEDBACK_STATUS_MAP: Record<string, { label: string; tone: string }> = {
  open: { label: '待处理', tone: 'warn' },
  processing: { label: '处理中', tone: 'info' },
  resolved: { label: '已解决', tone: 'ok' },
  closed: { label: '已关闭', tone: 'muted' },
}
