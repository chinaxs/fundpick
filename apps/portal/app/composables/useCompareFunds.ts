/**
 * 基金对比清单（最多 3 只）。
 *
 * 存在 cookie 而不是 localStorage：与登录态一致，SSR 首屏也能读到，
 * 分享/刷新不会丢；只存代码字符串，不存详情，避免陈旧数据。
 */
const COOKIE = 'compare_codes'
export const MAX_COMPARE = 3

export function useCompareFunds() {
  const raw = useCookie<string | null>(COOKIE, {
    maxAge: 60 * 60 * 24 * 30,
    sameSite: 'lax',
    path: '/',
  })

  const codes = computed(() =>
    (raw.value ?? '')
      .split(',')
      .map((code) => code.trim())
      .filter(Boolean),
  )
  const count = computed(() => codes.value.length)
  const canAdd = computed(() => count.value < MAX_COMPARE)

  /** 返回 false 表示已满或重复，调用方据此提示 */
  function add(code: string): boolean {
    const value = code.trim()
    if (!value || codes.value.includes(value) || !canAdd.value) return false
    raw.value = [...codes.value, value].join(',')
    return true
  }

  function remove(code: string) {
    raw.value = codes.value.filter((item) => item !== code).join(',')
  }

  function toggle(code: string): boolean {
    if (codes.value.includes(code)) {
      remove(code)
      return false
    }
    return add(code)
  }

  function clear() {
    raw.value = ''
  }

  return { codes, count, canAdd, add, remove, toggle, clear }
}
