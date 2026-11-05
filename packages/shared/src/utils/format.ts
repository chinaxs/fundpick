/** 通用格式化工具 */

/** 日期时间格式化：2026-11-05 14:30 */
export function formatDateTime(value?: string | number | Date | null): string {
  if (!value) return '-'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`
}

/** 仅日期：2026-11-05 */
export function formatDate(value?: string | number | Date | null): string {
  if (!value) return '-'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** 相对时间：3 分钟前 */
export function fromNow(value?: string | number | Date | null): string {
  if (!value) return '-'
  const date = value instanceof Date ? value : new Date(value)
  const diff = Date.now() - date.getTime()
  const minute = 60_000
  const hour = 60 * minute
  const day = 24 * hour

  if (diff < minute) return '刚刚'
  if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`
  if (diff < day) return `${Math.floor(diff / hour)} 小时前`
  if (diff < 30 * day) return `${Math.floor(diff / day)} 天前`
  return formatDate(date)
}

/** 截断文本，避免长摘要撑破布局 */
export function truncate(text: string, max = 80): string {
  return text.length > max ? `${text.slice(0, max)}…` : text
}

/** 把标题转成 URL 友好 slug（中文场景生成随机短码，与后端规则保持一致） */
export function toSlug(text: string): string {
  const ascii = text
    .normalize('NFKD')
    .replace(/[^\x00-\x7F]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
  return ascii || `post-${Math.random().toString(36).slice(2, 10)}`
}

/** 百分比，带正负号（用于收益类指标） */
export function fmtPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(digits)}%`
}

/** 幅度类指标（最大回撤、波动率）：取绝对值，不带正负号，避免被读成涨跌 */
export function fmtMagnitude(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '—'
  return `${Math.abs(value).toFixed(digits)}%`
}

/** 数值涨跌方向，用于配色（涨红跌绿） */
export function toneOf(value: number | null | undefined): 'up' | 'down' | 'neutral' {
  if (value === null || value === undefined || value === 0) return 'neutral'
  return value > 0 ? 'up' : 'down'
}
