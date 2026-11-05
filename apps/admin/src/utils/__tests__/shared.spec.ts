import { describe, expect, it } from 'vitest'
import {
  ARTICLE_STATUS_MAP,
  BIZ_CODE,
  formatDate,
  formatDateTime,
  toSlug,
  truncate,
} from '@project/shared'

/**
 * 冒烟测试：验证 workspace 依赖 @project/shared 能被正确解析与构建。
 * 共享包的函数被两个前端复用，这里做基础回归。
 */
describe('@project/shared', () => {
  it('格式化日期', () => {
    expect(formatDate('2026-11-05T10:30:00')).toBe('2026-11-05')
    expect(formatDateTime('2026-11-05T10:30:00')).toBe('2026-11-05 10:30')
    expect(formatDate(null)).toBe('-')
  })

  it('截断长文本', () => {
    expect(truncate('abcdef', 3)).toBe('abc…')
    expect(truncate('abc', 10)).toBe('abc')
  })

  it('生成 slug', () => {
    expect(toSlug('Hello World')).toBe('hello-world')
    // 中文退化为随机短码
    expect(toSlug('中文标题')).toMatch(/^post-[a-z0-9]+$/)
  })

  it('字典与业务码已对齐后端', () => {
    expect(Object.keys(ARTICLE_STATUS_MAP)).toEqual(['draft', 'published', 'archived'])
    expect(BIZ_CODE.ok).toBe(0)
    expect(BIZ_CODE.unauthorized).toBe(40100)
  })
})
