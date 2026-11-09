/** 共享交易弹窗，在基金所在页面完成买入；未登录时保留选择并先登录。 */
import type { TradeSeed } from '@project/shared'
export function useTradeDialog() {
  const seed = useState<TradeSeed | null>('portal:trade-dialog', () => null)
  const { isLoggedIn, openAuth } = useAuth()
  function open(value: TradeSeed) {
    seed.value = { ...value }
    if (!isLoggedIn.value) openAuth('login')
  }
  function close() {
    seed.value = null
  }
  return { seed, open, close }
}
