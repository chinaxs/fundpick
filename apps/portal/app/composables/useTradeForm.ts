/** 常用操作只记金额与时间；成交结果按需补全，不猜份额或费用。 */
import type { TradeInput, TradePreview, TradeSeed, TradeTiming } from '@project/shared'
function beijingInput(value = new Date().toISOString()) {
  return new Date(new Date(value).getTime() + 8 * 3600_000).toISOString().slice(0, 19)
}
export function useTradeForm(seed: TradeSeed, completed: (message?: string) => void) {
  const form = reactive({
    code: seed.code ?? '',
    kind: seed.kind,
    stage:
      seed.application_id || seed.legacy_position_id
        ? 'receipt'
        : ('pending' as 'receipt' | 'pending'),
    submitted_at: beijingInput(seed.submitted_at),
    platform: seed.platform ?? '',
    adjusted: seed.pricing_rule === 'platform',
    confirmed_on: seed.confirmed_on ?? '',
    settled_on: '',
    nav_mode: 'official' as 'official' | 'manual',
    nav: '',
    amount: seed.amount ? String(seed.amount) : '',
    shares: seed.requested_shares ?? '',
    confirmed_shares: '',
    received_amount: '',
    fee: '',
    receipt_ref: '',
    note: '',
  })
  const quote = ref<TradePreview | null>(null)
  const submitted = ref<TradeInput | null>(null)
  const timing = ref<TradeTiming | null>(null)
  const timingError = ref('')
  const timingBusy = ref(false)
  const busy = ref(false)
  const error = ref('')
  let requestKey = ''
  let applicationKey = ''
  let timer: ReturnType<typeof setTimeout> | undefined
  let version = 0
  const submittedTime = () => `${form.submitted_at}+08:00`
  const pricingRule = () => (form.adjusted ? 'platform' : 'auto')
  async function updateTiming() {
    const revision = ++version
    timing.value = null
    timingError.value = ''
    if (!/^\d{6}$/.test(form.code) || !form.submitted_at) {
      timingBusy.value = false
      return
    }
    timingBusy.value = true
    try {
      const result = await checkTradeTiming({
        code: form.code,
        submitted_at: submittedTime(),
        pricing_rule: pricingRule(),
      })
      if (revision !== version) return
      timing.value = result
      if (result.expected_nav_on) form.confirmed_on = result.expected_nav_on
      form.nav_mode = result.official_nav && !form.adjusted ? 'official' : 'manual'
    } catch (err) {
      if (revision === version) timingError.value = tradeError(err)
    } finally {
      if (revision === version) timingBusy.value = false
    }
  }
  watch(
    () => [form.code, form.submitted_at, form.adjusted],
    () => {
      version++
      clearTimeout(timer)
      timing.value = null
      timingError.value = ''
      timer = setTimeout(updateTiming, 250)
    },
    { immediate: true },
  )
  watch(
    () => [
      form.code,
      form.kind,
      form.submitted_at,
      form.platform,
      form.amount,
      form.shares,
      form.note,
      form.adjusted,
    ],
    () => {
      applicationKey = ''
    },
  )
  onBeforeUnmount(() => {
    version++
    clearTimeout(timer)
  })
  async function preview() {
    if (busy.value) return
    error.value = ''
    busy.value = true
    try {
      if (form.stage === 'pending') {
        if (!applicationKey) applicationKey = crypto.randomUUID()
        const result = await saveAutomaticTrade({
          code: form.code.trim(),
          kind: form.kind,
          submitted_at: submittedTime(),
          platform: form.platform.trim() || null,
          pricing_rule: pricingRule(),
          ...(form.kind === 'buy' ? { amount: form.amount } : { shares: form.shares }),
          request_key: applicationKey,
          note: form.note.trim() || null,
        })
        completed(result.message)
        return
      }
      if (!timing.value) throw new Error(timingError.value || '正在核对购买时间，请稍候')
      const input: TradeInput = {
        code: form.code.trim(),
        kind: form.kind,
        record_source: 'receipt',
        submitted_at: submittedTime(),
        ...(form.settled_on ? { settled_on: form.settled_on } : {}),
        platform: form.platform.trim(),
        pricing_rule: timing.value.pricing_rule,
        confirmed_on: form.confirmed_on,
        nav_mode: form.nav_mode,
        ...(form.nav_mode === 'manual' ? { nav: form.nav } : {}),
        ...(form.kind === 'buy'
          ? { amount: form.amount, confirmed_shares: form.confirmed_shares }
          : { shares: form.shares, received_amount: form.received_amount }),
        fee: form.fee,
        receipt_ref: form.receipt_ref || undefined,
        ...(timing.value.pricing_rule === 'platform'
          ? { date_reason: '按用户填写的平台成交信息' }
          : {}),
        note: form.note.trim() || null,
        ...(seed.application_id ? { application_id: seed.application_id } : {}),
        ...(seed.legacy_position_id ? { legacy_position_id: seed.legacy_position_id } : {}),
      }
      quote.value = await previewTrade(input)
      submitted.value = input
      requestKey = crypto.randomUUID()
    } catch (err) {
      error.value = tradeError(err)
    } finally {
      busy.value = false
    }
  }
  async function confirm() {
    if (!quote.value || !submitted.value || busy.value) return
    busy.value = true
    error.value = ''
    try {
      await confirmTrade({
        request: submitted.value,
        preview_hash: quote.value.preview_hash,
        request_key: requestKey,
      })
      completed()
    } catch (err) {
      error.value = tradeError(err)
      if ((err as { statusCode?: number }).statusCode === 409) quote.value = null
    } finally {
      busy.value = false
    }
  }
  /** 无需额外确认无差异的回执；数据差异必须由用户核对后保存。 */
  async function save() {
    await preview()
    if (
      quote.value &&
      !quote.value.warnings.some((item) => item.includes('差异') || item.includes('不一致'))
    ) {
      await confirm()
    }
  }
  function edit() {
    quote.value = null
    error.value = ''
  }
  return {
    form,
    quote,
    submitted,
    timing,
    timingError,
    timingBusy,
    busy,
    error,
    preview,
    save,
    confirm,
    edit,
  }
}
export type ReceiptForm = ReturnType<typeof useTradeForm>['form']
