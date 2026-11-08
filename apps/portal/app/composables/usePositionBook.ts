/** 持仓页状态：筛选/分页与本地记录操作；待入账自动刷新，不要求补充成交结果。 */
import type { TradeHistoryItem, TradeHistoryQuery } from '@project/shared'
import { ElMessage, ElMessageBox } from 'element-plus'

export async function usePositionBook() {
  const { user, isLoggedIn } = useAuth()
  const view = ref<'holdings' | 'history'>('holdings')
  const page = ref(1)
  const pageSize = ref(20)
  const filters = reactive({
    keyword: '',
    kind: '' as '' | 'buy' | 'sell',
    status: '' as '' | TradeHistoryItem['status'],
    dates: [] as string[],
  })
  const params = computed<TradeHistoryQuery>(() => ({
    page: page.value,
    page_size: pageSize.value,
    keyword: filters.keyword.trim() || undefined,
    kind: filters.kind || undefined,
    status: filters.status || undefined,
    start: filters.dates?.[0] || undefined,
    end: filters.dates?.[1] || undefined,
  }))
  watch(
    () => [filters.keyword, filters.kind, filters.status, filters.dates, pageSize.value],
    () => {
      page.value = 1
    },
    { flush: 'sync' },
  )
  const portfolio = usePortfolio()
  const history = useTransactions(
    params,
    computed(() => view.value === 'history'),
  )
  const applications = useTradeApplications()
  const { load: loadHoldings } = useHoldingStatus()
  const refreshing = ref(false)
  const actionBusy = ref(false)
  watch(
    () => user.value?.id,
    () => {
      reset()
      view.value = 'holdings'
    },
  )
  watch(history.data, (result) => {
    if (result)
      page.value = Math.min(page.value, Math.max(1, Math.ceil(result.total / pageSize.value)))
  })
  async function refreshBook() {
    await Promise.all([
      portfolio.refresh(),
      history.refresh(),
      loadHoldings(true),
      refreshNuxtData(`me-dashboard-${user.value?.id}`),
    ])
  }
  watch(
    () => (applications.data.value ?? []).map((item) => item.id).join(','),
    (next, previous) => {
      if (previous !== undefined && next !== previous && isLoggedIn.value) refreshBook()
    },
  )
  async function reload() {
    if (refreshing.value) return
    refreshing.value = true
    try {
      await applications.refresh()
      await refreshBook()
    } finally {
      refreshing.value = false
    }
  }
  function reset() {
    filters.keyword = ''
    filters.kind = ''
    filters.status = ''
    filters.dates = []
    page.value = 1
  }
  async function cancelApplication(id: number) {
    if (actionBusy.value) return
    try {
      await ElMessageBox.confirm(
        '撤销后本站停止自动入账。此操作不会向购买平台发起撤单，外部平台撤单请按其受理状态与时限操作。',
        '撤销本站记录',
        { confirmButtonText: '撤销记录', cancelButtonText: '保留' },
      )
    } catch {
      return
    }
    actionBusy.value = true
    try {
      await cancelTradeApplication(id)
      await applications.refresh()
      await refreshBook()
      ElMessage.success('记录已撤销')
    } catch (err) {
      ElMessage.error(tradeError(err))
      await reload()
    } finally {
      actionBusy.value = false
    }
  }
  async function voidRecord(item: TradeHistoryItem) {
    if (actionBusy.value) return
    let reason: string
    try {
      const result = await ElMessageBox.prompt(
        `作废「${item.name}」后，本站按剩余记录重新汇总持仓。已入账记录的纠错不等同于平台撤单。`,
        '记录纠错',
        {
          inputPlaceholder: '填写记错的原因',
          inputValidator: (value) => !!value?.trim() || '请填写原因',
          confirmButtonText: '作废记录',
          cancelButtonText: '取消',
        },
      )
      reason = result.value
    } catch {
      return
    }
    actionBusy.value = true
    try {
      await voidTrade(item.id, reason)
      await applications.refresh()
      await refreshBook()
      ElMessage.success('记录已作废')
    } catch (err) {
      ElMessage.error(tradeError(err))
    } finally {
      actionBusy.value = false
    }
  }
  async function removeRecord(item: TradeHistoryItem) {
    if (actionBusy.value) return
    try {
      await ElMessageBox.confirm(
        `删除「${item.name}」这条${item.status === 'voided' ? '已作废' : '已撤销'}记录？不会影响持仓和收益。`,
        '删除记录',
        { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
    actionBusy.value = true
    try {
      await deleteTradeRecord(item)
      await history.refresh()
      ElMessage.success('记录已删除')
    } catch (err) {
      ElMessage.error(tradeError(err))
    } finally {
      actionBusy.value = false
    }
  }
  let timer: ReturnType<typeof setInterval> | undefined
  function poll() {
    if (
      !document.hidden &&
      isLoggedIn.value &&
      !actionBusy.value &&
      !refreshing.value &&
      (applications.data.value ?? []).some((item) => item.automatic_processing)
    )
      reload()
  }
  onMounted(() => {
    timer = setInterval(poll, 30_000)
    document.addEventListener('visibilitychange', poll)
  })
  onBeforeUnmount(() => {
    clearInterval(timer)
    document.removeEventListener('visibilitychange', poll)
  })
  await Promise.all([portfolio, history, applications])
  return {
    view,
    page,
    pageSize,
    filters,
    portfolio,
    history,
    applications,
    refreshing,
    actionBusy,
    reload,
    reset,
    cancelApplication,
    voidRecord,
    removeRecord,
  }
}
