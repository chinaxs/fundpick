/** 录入界面的校验与显示；金额只校验，不改变用户填写的精度。 */
import type { FormRules } from 'element-plus'
import type { ReceiptForm } from './useTradeForm'

export function useTradeEntry(form: ReceiptForm) {
  const editingTime = ref(false)
  function numberRule(label: string, digits: number, maximum: number, zero = false) {
    return {
      validator: (_rule: unknown, value: string, done: (error?: Error) => void) => {
        const pattern = new RegExp(`^\\d+(?:\\.\\d{1,${digits}})?$`)
        const amount = Number(value)
        if (
          !pattern.test(value) ||
          !Number.isFinite(amount) ||
          (zero ? amount < 0 : amount <= 0) ||
          amount > maximum
        ) {
          done(new Error(`请填写${label}，最多${digits}位小数`))
        } else done()
      },
      trigger: 'blur',
    }
  }
  const rules: FormRules<ReceiptForm> = {
    code: [{ required: true, pattern: /^\d{6}$/, message: '请输入6位基金代码', trigger: 'blur' }],
    amount: [numberRule('买入金额', 2, 100_000_000)],
    shares: [numberRule('卖出份额', 4, 1_000_000_000)],
    submitted_at: [{ required: true, message: '请选择下单时间', trigger: 'change' }],
    platform: [
      {
        validator: (_rule, value: string, done) =>
          done(value.trim() ? undefined : new Error('请填写交易平台')),
        trigger: 'blur',
      },
    ],
    confirmed_shares: [numberRule('确认份额', 4, 1_000_000_000)],
    received_amount: [numberRule('到账金额', 2, 100_000_000, true)],
    fee: [numberRule('实际手续费，无费用填0', 2, 100_000_000, true)],
    nav: [numberRule('成交净值', 6, 1_000_000)],
    confirmed_on: [{ required: true, message: '请选择平台显示的净值日期', trigger: 'change' }],
  }
  const timeLabel = computed(() => {
    if (!form.submitted_at) return '选择购买时间'
    const [date, time] = form.submitted_at.split('T')
    const today = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(new Date())
    return `${date === today ? '今天' : date} ${time}`
  })
  return { editingTime, rules, timeLabel }
}
