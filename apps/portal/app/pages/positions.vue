<script setup lang="ts">
import type { ApiResponse, FundDetail, PositionItem } from '@project/shared'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fmtPct, toneOf } from '@project/shared'
import { useApiBase } from '~/composables/usePortalApi'

const { isLoggedIn, openAuth, ensureSession } = useAuth()
await ensureSession()

const { data, pending, refresh } = await usePositions()
const items = computed(() => data.value?.items ?? [])
const summary = computed(() => data.value?.summary)

// ---------------------------------------------------------------- 表单
const showForm = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const form = reactive({
  code: '',
  amount: '',
  bought_at: new Date().toISOString().slice(0, 10),
  note: '',
})

/** 代码输入后先查一下基金名称，避免小白填错代码 */
const fundPreview = ref<{ name: string; latest_nav_date: string | null } | null>(null)
async function lookupFund() {
  fundPreview.value = null
  const code = form.code.trim()
  if (!/^\d{6}$/.test(code)) return
  try {
    const res = await $fetch<ApiResponse<FundDetail>>(`/portal/funds/${code}`, {
      baseURL: useApiBase(),
    })
    if (res.data) {
      fundPreview.value = {
        name: res.data.name,
        latest_nav_date: res.data.latest_nav_date,
      }
    }
  } catch {
    fundPreview.value = null
  }
}

function resetForm() {
  showForm.value = false
  editingId.value = null
  form.code = ''
  form.amount = ''
  form.bought_at = new Date().toISOString().slice(0, 10)
  form.note = ''
  fundPreview.value = null
}

function openCreate() {
  resetForm()
  showForm.value = true
}

function openEdit(item: PositionItem) {
  resetForm()
  editingId.value = item.id
  form.code = item.code
  form.amount = String(item.amount)
  form.bought_at = item.bought_at
  form.note = item.note ?? ''
  fundPreview.value = { name: item.name, latest_nav_date: item.latest_nav_date }
  showForm.value = true
}

async function submit() {
  const amount = Number(form.amount)
  if (!form.code.trim() || !/^\d{6}$/.test(form.code.trim())) {
    ElMessage.warning('请填写 6 位基金代码')
    return
  }
  if (!amount || amount <= 0) {
    ElMessage.warning('请填写买入金额')
    return
  }

  saving.value = true
  try {
    if (editingId.value) {
      const updated = await updatePosition(editingId.value, {
        amount,
        bought_at: form.bought_at,
        note: form.note.trim() || null,
      })
      ElMessage.success(navMessage(updated))
    } else {
      const created = await createPosition({
        code: form.code.trim(),
        amount,
        bought_at: form.bought_at,
        note: form.note.trim() || null,
      })
      ElMessage.success(navMessage(created))
    }
    resetForm()
    await refresh()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败，请检查基金代码与日期')
  } finally {
    saving.value = false
  }
}

async function remove(item: PositionItem) {
  try {
    await ElMessageBox.confirm(`确定删除「${item.name}」这笔模拟持仓吗？`, '删除持仓', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deletePosition(item.id)
    ElMessage.success('已删除')
    await refresh()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '删除失败')
  }
}

// ---------------------------------------------------------------- 展示
function money(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function signedMoney(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${money(value)}`
}

function sourceText(source: string): string {
  return source === 'history' ? '历史净值' : '最新净值'
}

function navMessage(item: PositionItem): string {
  const base = `${item.cost_nav_date ?? '最近交易日'} 净值 ${item.cost_nav.toFixed(4)}`
  if (item.nav_source === 'latest') {
    return `该基金暂无历史净值序列，已按最新净值（${base}）估算，折算 ${item.shares.toFixed(2)} 份`
  }
  return `已按 ${base} 自动折算 ${item.shares.toFixed(2)} 份`
}

async function reload() {
  await refresh()
}

useSeoMeta({
  title: '模拟持仓',
  description: '只记录买入金额与日期，系统自动查询当日净值并折算份额，跟踪模拟持仓的市值与盈亏。',
})
</script>

<template>
  <div class="page">
    <div class="container">
      <header class="head">
        <div>
          <p class="section__eyebrow">Portfolio</p>
          <h1 class="head__title">模拟持仓 <span class="badge">模拟</span></h1>
          <p class="head__sub">
            只填「买了多少钱 + 哪天买的」，净值由系统按历史数据自动查询，份额和盈亏自动算
          </p>
        </div>
        <button v-if="isLoggedIn" type="button" class="btn btn--primary" @click="openCreate">
          + 记一笔持仓
        </button>
      </header>

      <MemberNav />

      <!-- 未登录 -->
      <section v-if="!isLoggedIn" class="empty">
        <div class="empty__icon">◈</div>
        <h2 class="empty__title">登录后记录模拟持仓</h2>
        <p class="empty__desc">不用开通交易，也不用懂净值，填金额和日期就能跟踪盈亏。</p>
        <button type="button" class="btn btn--primary" @click="openAuth('login')">
          登录 / 注册
        </button>
      </section>

      <template v-else>
        <!-- 汇总 -->
        <section class="card summary-card">
          <div class="summary-card__item">
            <span class="summary-card__label">持仓笔数</span>
            <span class="summary-card__value num">{{ summary?.count ?? 0 }}</span>
          </div>
          <div class="summary-card__item">
            <span class="summary-card__label">总投入成本</span>
            <span class="summary-card__value num">¥ {{ money(summary?.total_amount) }}</span>
          </div>
          <div class="summary-card__item">
            <span class="summary-card__label">当前市值</span>
            <span class="summary-card__value num">¥ {{ money(summary?.total_market_value) }}</span>
          </div>
          <div class="summary-card__item">
            <span class="summary-card__label">浮动盈亏</span>
            <span class="summary-card__value num" :class="toneOf(summary?.total_profit)">
              {{ signedMoney(summary?.total_profit) }}
            </span>
          </div>
          <div class="summary-card__item">
            <span class="summary-card__label">总收益率</span>
            <span class="summary-card__value num" :class="toneOf(summary?.profit_rate)">
              {{ fmtPct(summary?.profit_rate) }}
            </span>
          </div>
        </section>

        <!-- 录入表单 -->
        <section v-if="showForm" class="card form-card">
          <div class="form-card__head">
            <strong>{{ editingId ? '编辑持仓' : '记一笔模拟持仓' }}</strong>
            <span>净值由系统按买入日期自动查，无需手动填写</span>
          </div>

          <div class="form-grid">
            <label class="field">
              <span>基金代码</span>
              <input
                v-model="form.code"
                class="input"
                inputmode="numeric"
                maxlength="6"
                placeholder="6 位数字，如 021180"
                :disabled="!!editingId"
                @blur="lookupFund"
              />
              <small v-if="fundPreview" class="field__hint">
                {{ fundPreview.name }} · 最新净值日期 {{ fundPreview.latest_nav_date ?? '—' }}
              </small>
            </label>

            <label class="field">
              <span>买入金额（元）</span>
              <input
                v-model="form.amount"
                class="input"
                type="number"
                min="0.01"
                step="0.01"
                placeholder="例如 10000"
              />
            </label>

            <label class="field">
              <span>买入日期</span>
              <input
                v-model="form.bought_at"
                class="input"
                type="date"
                :max="new Date().toISOString().slice(0, 10)"
              />
              <small class="field__hint">非交易日自动按上一交易日净值折算</small>
            </label>

            <label class="field">
              <span>备注（可选）</span>
              <input v-model="form.note" class="input" placeholder="记录一下建仓理由" />
            </label>
          </div>

          <div class="form-card__foot">
            <span class="form-card__tip">
              系统会查该基金在买入日期当天（或之前最近交易日）的单位净值， 用「金额 ÷
              净值」自动折算份额
            </span>
            <div class="form-card__buttons">
              <button type="button" class="btn" @click="resetForm">取消</button>
              <button type="button" class="btn btn--primary" :disabled="saving" @click="submit">
                {{ saving ? '保存中…' : editingId ? '保存修改' : '添加持仓' }}
              </button>
            </div>
          </div>
        </section>

        <!-- 明细 -->
        <section class="card list-card">
          <div class="list-card__head">
            <div>
              <h2 class="list-card__title">持仓明细</h2>
              <p class="list-card__sub">市值按最新单位净值估算，不代表真实交易</p>
            </div>
            <button v-if="items.length" type="button" class="btn" @click="reload">刷新</button>
          </div>

          <div v-if="pending" class="skeleton">
            <div v-for="i in 3" :key="i" class="skeleton__row" />
          </div>

          <div v-else-if="!items.length" class="empty-state">
            <div class="empty-state__icon">◈</div>
            <div class="empty-state__title">还没有模拟持仓</div>
            <p class="empty-state__desc">
              点右上角「记一笔持仓」，只填买入金额和日期即可开始跟踪盈亏。
            </p>
            <button type="button" class="btn btn--primary" @click="openCreate">记一笔持仓</button>
          </div>

          <div v-else class="table-wrap">
            <table class="data-table wide-table">
              <thead>
                <tr>
                  <th>基金</th>
                  <th class="ta-r">买入金额</th>
                  <th>买入日期</th>
                  <th class="ta-r">折算净值</th>
                  <th class="ta-r">份额</th>
                  <th class="ta-r">最新净值</th>
                  <th class="ta-r">当前市值</th>
                  <th class="ta-r">浮动盈亏</th>
                  <th class="ta-r">收益率</th>
                  <th class="ta-c">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in items" :key="item.id">
                  <td>
                    <NuxtLink :to="`/funds/${item.code}`" class="fund-link">{{
                      item.name
                    }}</NuxtLink>
                    <span class="fund-code num">{{ item.code }}</span>
                  </td>
                  <td class="ta-r num">{{ money(item.amount) }}</td>
                  <td class="num muted">{{ item.bought_at }}</td>
                  <td class="ta-r num">
                    {{ item.cost_nav.toFixed(4) }}
                    <span class="cell-sub">
                      {{ item.cost_nav_date ?? '—' }} · {{ sourceText(item.nav_source) }}
                    </span>
                  </td>
                  <td class="ta-r num">{{ item.shares.toFixed(2) }}</td>
                  <td class="ta-r num">{{ item.latest_nav?.toFixed(4) ?? '—' }}</td>
                  <td class="ta-r num">{{ money(item.market_value) }}</td>
                  <td class="ta-r num" :class="toneOf(item.profit)">
                    {{ signedMoney(item.profit) }}
                  </td>
                  <td class="ta-r num" :class="toneOf(item.profit_rate)">
                    {{ fmtPct(item.profit_rate) }}
                  </td>
                  <td class="ta-c">
                    <div class="row-actions">
                      <button type="button" class="row-btn" @click="openEdit(item)">编辑</button>
                      <button type="button" class="row-btn row-btn--danger" @click="remove(item)">
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
            <p class="table-note">
              {{ summary?.valued_count ?? 0 }} / {{ summary?.count ?? 0 }} 笔已取得最新净值；
              未取到最新净值的持仓不计入市值汇总。买入日期早于本地净值采集起点时，
              系统回退到最新净值并在「折算净值」列标注来源。
            </p>
          </div>
        </section>

        <p class="disclaimer">
          模拟持仓仅用于个人记录与估算，不涉及任何真实交易或资金往来。
          净值数据来源于公开渠道，可能存在延迟或误差，不构成投资建议。
        </p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 40px 0 48px;
}

.head {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-end;
  justify-content: space-between;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--line-soft);
}

.head__title {
  margin: 6px 0 0;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.head__sub {
  margin: 9px 0 0;
  max-width: 620px;
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--muted);
}

.badge {
  display: inline-block;
  padding: 3px 8px;
  margin-left: 6px;
  font-size: 11px;
  font-weight: 600;
  color: #b45309;
  vertical-align: middle;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 6px;
}

/* 汇总 */
.summary-card {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  padding: 20px 22px;
  margin-bottom: 16px;
}

.summary-card__item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-card__label {
  font-size: 12px;
  color: var(--muted-2);
}

.summary-card__value {
  font-size: 20px;
  font-weight: 700;
}

/* 表单 */
.form-card {
  padding: 20px 22px;
  margin-bottom: 16px;
  border-color: #bfdbfe;
}

.form-card__head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 16px;
  font-size: 14px;
}

.form-card__head span {
  font-size: 12px;
  color: var(--muted-2);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.field {
  display: grid;
  gap: 6px;
  font-size: 12.5px;
  color: var(--muted);
}

.field__hint {
  font-size: 11px;
  color: var(--muted-2);
}

.input {
  width: 100%;
  height: 38px;
  padding: 0 11px;
  font-size: 13.5px;
  color: var(--ink);
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 8px;
  outline: none;
}

.input:focus {
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgb(59 130 246 / 10%);
}

.input:disabled {
  color: var(--muted);
  background: var(--bg-soft);
}

.form-card__foot {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
}

.form-card__tip {
  max-width: 560px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--brand);
}

.form-card__buttons {
  display: flex;
  gap: 8px;
}

/* 明细 */
.list-card {
  padding: 20px 22px;
}

.list-card__head {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.list-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.list-card__sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--muted);
}

.table-wrap {
  overflow-x: auto;
}

.wide-table {
  min-width: 1040px;
  font-size: 12.5px;
}

.ta-r {
  text-align: right;
}

.ta-c {
  text-align: center;
}

.fund-link {
  font-size: 13px;
  color: var(--ink);
}

.fund-link:hover {
  color: var(--brand);
}

.fund-code {
  display: block;
  font-size: 11px;
  color: var(--muted-2);
}

.cell-sub {
  display: block;
  font-size: 10.5px;
  color: var(--muted-2);
}

.muted {
  color: var(--muted);
}

.up {
  color: var(--up);
  font-weight: 600;
}

.down {
  color: var(--down);
  font-weight: 600;
}

.row-actions {
  display: inline-flex;
  gap: 5px;
  justify-content: center;
}

.row-btn {
  height: 26px;
  padding: 0 9px;
  font-size: 11.5px;
  color: var(--ink-2);
  cursor: pointer;
  white-space: nowrap;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 6px;
}

.row-btn:hover {
  color: var(--brand);
  border-color: var(--brand);
}

.row-btn--danger:hover {
  color: #dc2626;
  border-color: #fecaca;
}

.table-note {
  margin: 12px 0 0;
  font-size: 11.5px;
  line-height: 1.8;
  color: var(--muted-2);
}

/* 骨架 / 空态 */
.skeleton {
  display: grid;
  gap: 10px;
}

.skeleton__row {
  height: 48px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 37%, #f1f5f9 63%);
  background-size: 400% 100%;
  border-radius: 8px;
  animation: shimmer 1.4s ease infinite;
}

@keyframes shimmer {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0 50%;
  }
}

.empty-state {
  padding: 56px 20px;
  text-align: center;
  background: var(--bg-soft);
  border: 1px dashed var(--line);
  border-radius: 10px;
}

.empty-state__icon {
  font-size: 32px;
  color: #cbd5e1;
}

.empty-state__title {
  margin-top: 8px;
  font-size: 16px;
  font-weight: 600;
}

.empty-state__desc {
  margin: 8px 0 20px;
  font-size: 13px;
  color: var(--muted);
}

.empty {
  padding: 72px 24px;
  text-align: center;
  background: var(--bg-soft);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

.empty__icon {
  font-size: 34px;
  color: #cbd5e1;
}

.empty__title {
  margin-top: 8px;
  font-size: 17px;
  font-weight: 600;
}

.empty__desc {
  margin: 8px 0 22px;
  font-size: 13.5px;
  color: var(--muted);
}

.disclaimer {
  margin-top: 22px;
  font-size: 12px;
  line-height: 1.9;
  color: var(--muted-2);
  text-align: center;
}

@media (max-width: 900px) {
  .summary-card {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .form-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .summary-card {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .head__title {
    font-size: 25px;
  }
}
</style>
