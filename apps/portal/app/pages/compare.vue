<script setup lang="ts">
import type { ApiResponse, FundCompareResult, FundListItem, PageResult } from '@project/shared'

/**
 * 基金对比：最多 3 只，重点看费率、回撤、风险与区间表现。
 * 区间指标缺失时显示「无数据」，不把空值当 0。
 */
const { codes, count, canAdd, add, remove, clear } = useCompareFunds()
const apiBase = useApiBase()

const keyword = ref('')
const results = ref<FundListItem[]>([])
const searching = ref(false)
const slotOpen = ref(false)
const message = ref('')

const { data, pending, error, refresh } = await useAsyncData<FundCompareResult | null>(
  'portal-compare',
  async () => {
    if (codes.value.length < 2) return null
    const res = await $fetch<ApiResponse<FundCompareResult>>('/portal/funds/compare', {
      baseURL: apiBase,
      query: { codes: codes.value.join(',') },
    })
    return res.data
  },
  { watch: [codes] },
)

function fmt(value: number | null | undefined, suffix = '') {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(2)}${suffix}`
}

const infoRows = computed(() => {
  const items = data.value?.items ?? []
  if (!items.length) return []
  return [
    { label: '类型', values: items.map((item) => item.type_label) },
    { label: '风险等级', values: items.map((item) => item.risk_label ?? '—') },
    { label: '份额类别', values: items.map((item) => item.share_class ?? '无份额区分') },
    { label: '基金公司', values: items.map((item) => item.company_name ?? '—') },
    { label: '基金经理', values: items.map((item) => item.manager_name ?? '—') },
    { label: '最新净值', values: items.map((item) => fmt(item.latest_nav)) },
    { label: '净值日期', values: items.map((item) => item.latest_nav_date ?? '—') },
    { label: '规模（亿元）', values: items.map((item) => fmt(item.scale)) },
    {
      label: '管理费率（%/年）',
      values: items.map((item) => fmt(item.fee_rate)),
      hint: '按年计提，不含申购费与销售服务费',
    },
    { label: '托管费率（%/年）', values: items.map((item) => fmt(item.custody_fee)) },
    { label: '成立日期', values: items.map((item) => item.inception_date ?? '—') },
  ]
})

const periodLabels = computed(() => data.value?.items[0]?.periods ?? [])

function periodValue(code: string, period: string, key: 'return_rate' | 'max_drawdown' | 'sharpe') {
  const item = data.value?.items.find((entry) => entry.code === code)
  const row = item?.periods.find((entry) => entry.period === period)
  if (!row) return { text: '—', missing: true }
  if (key !== 'return_rate' && !row.available) return { text: '无数据', missing: true }
  const value = row[key]
  return value === null || value === undefined
    ? { text: '—', missing: true }
    : {
        text: fmt(value, key === 'return_rate' || key === 'max_drawdown' ? '%' : ''),
        missing: false,
      }
}

function riskDate(code: string, period: string) {
  const item = data.value?.items.find((entry) => entry.code === code)
  return item?.periods.find((entry) => entry.period === period)?.risk_nav_date ?? null
}

async function runSearch() {
  const text = keyword.value.trim()
  if (!text) return
  searching.value = true
  message.value = ''
  try {
    const res = await $fetch<ApiResponse<PageResult<FundListItem>>>('/portal/funds', {
      baseURL: apiBase,
      query: { keyword: text, page_size: 8 },
    })
    results.value = res.data?.items ?? []
    if (!results.value.length) message.value = '没有匹配的基金，试试代码或全称。'
  } catch {
    message.value = '搜索失败，请稍后重试。'
  } finally {
    searching.value = false
  }
}

function pick(fund: FundListItem) {
  const added = add(fund.code)
  if (!added) {
    message.value = codes.value.includes(fund.code) ? '该基金已在对比中。' : '最多对比 3 只基金。'
    return
  }
  message.value = ''
  keyword.value = ''
  results.value = []
  slotOpen.value = false
}

function removeAt(code: string) {
  remove(code)
}

useSeoMeta({
  title: '基金对比',
  description: '横向比较最多 3 只基金的费用、回撤与区间表现。',
})
</script>

<template>
  <div class="compare">
    <div class="container">
      <header class="head">
        <div>
          <h1>基金对比</h1>
          <p class="head__sub">
            最多 3 只。重点看费率、回撤与风险指标；区间缺失会明确标注，不当作 0。
          </p>
        </div>
        <button v-if="count" type="button" class="text-btn" @click="clear">清空</button>
      </header>

      <!-- 选择区 -->
      <section class="slots">
        <div v-for="(code, index) in codes" :key="code" class="slot slot--filled">
          <div class="slot__head">
            <span class="slot__index">{{ index + 1 }}</span>
            <button type="button" class="slot__remove" @click="removeAt(code)">移除</button>
          </div>
          <div class="slot__name">{{ data?.items.find((i) => i.code === code)?.name ?? code }}</div>
          <div class="slot__code">{{ code }}</div>
        </div>

        <button v-if="canAdd" type="button" class="slot slot--empty" @click="slotOpen = !slotOpen">
          <span class="slot__plus">+</span>
          <span>添加基金（{{ count }}/3）</span>
        </button>
      </section>

      <section v-if="slotOpen" class="picker card">
        <div class="picker__form">
          <input
            v-model="keyword"
            class="picker__input"
            placeholder="输入基金代码、名称或拼音首字母"
            @keyup.enter="runSearch"
          />
          <button type="button" class="btn" :disabled="searching" @click="runSearch">
            {{ searching ? '搜索中…' : '搜索' }}
          </button>
        </div>
        <p v-if="message" class="hint">{{ message }}</p>
        <ul v-if="results.length" class="picker__list">
          <li v-for="fund in results" :key="fund.code">
            <button type="button" class="picker__item" @click="pick(fund)">
              <span class="picker__name">{{ fund.name }}</span>
              <span class="picker__meta">
                {{ fund.code }} · {{ fund.type }}
                <template v-if="fund.share_class"> · {{ fund.share_class }} 类</template>
              </span>
            </button>
          </li>
        </ul>
      </section>

      <!-- 结果 -->
      <p v-if="error" class="hint hint--error" role="alert">
        对比数据加载失败，请稍后重试。
        <button type="button" class="text-btn" @click="refresh()">重新加载</button>
      </p>

      <section v-else-if="count < 2" class="empty">
        <h2>至少选择 2 只基金</h2>
        <p>先添加两只以上，才能看到横向对比。</p>
      </section>

      <p v-else-if="pending" class="hint">正在加载对比数据…</p>

      <template v-else-if="data">
        <div class="table-wrap card">
          <table class="table">
            <thead>
              <tr>
                <th class="table__label">指标</th>
                <th v-for="item in data.items" :key="item.code">
                  <NuxtLink :to="`/funds/${item.code}`" class="table__fund">{{
                    item.name
                  }}</NuxtLink>
                  <div class="table__code">{{ item.code }}</div>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in infoRows" :key="row.label">
                <th class="table__label">
                  {{ row.label }}
                  <span v-if="'hint' in row && row.hint" class="table__hint">{{ row.hint }}</span>
                </th>
                <td v-for="(value, index) in row.values" :key="index">{{ value }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-for="period in periodLabels" :key="period.period" class="table-wrap card">
          <h2 class="period__title">
            {{ period.label }}
            <span class="period__hint">风险指标为空时显示「无数据」，表示上游未提供</span>
          </h2>
          <table class="table">
            <thead>
              <tr>
                <th class="table__label">指标</th>
                <th v-for="item in data.items" :key="item.code">{{ item.code }}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th class="table__label">区间收益</th>
                <td v-for="item in data.items" :key="item.code">
                  {{ periodValue(item.code, period.period, 'return_rate').text }}
                </td>
              </tr>
              <tr>
                <th class="table__label">最大回撤</th>
                <td v-for="item in data.items" :key="item.code">
                  <span
                    :class="{
                      'is-missing': periodValue(item.code, period.period, 'max_drawdown').missing,
                    }"
                  >
                    {{ periodValue(item.code, period.period, 'max_drawdown').text }}
                  </span>
                </td>
              </tr>
              <tr>
                <th class="table__label">夏普比率</th>
                <td v-for="item in data.items" :key="item.code">
                  <span
                    :class="{
                      'is-missing': periodValue(item.code, period.period, 'sharpe').missing,
                    }"
                  >
                    {{ periodValue(item.code, period.period, 'sharpe').text }}
                  </span>
                </td>
              </tr>
              <tr>
                <th class="table__label">风险数据日期</th>
                <td v-for="item in data.items" :key="item.code">
                  {{ riskDate(item.code, period.period) ?? '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p class="note">{{ data.note }}</p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.compare {
  padding: 32px 0 64px;
}

.head {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 20px;
}

.head h1 {
  margin: 0 0 6px;
  font-size: 26px;
}

.head__sub {
  margin: 0;
  font-size: 14px;
  color: var(--muted);
}

.text-btn {
  padding: 0;
  font-size: 13px;
  color: var(--brand);
  cursor: pointer;
  background: none;
  border: none;
}

.btn {
  padding: 9px 18px;
  font-size: 14px;
  color: #fff;
  cursor: pointer;
  background: var(--brand);
  border: none;
  border-radius: 999px;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.card {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-xs);
}

.slots {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.slot {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 96px;
  padding: 14px;
  text-align: left;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.slot--empty {
  align-items: center;
  justify-content: center;
  color: var(--muted);
  cursor: pointer;
  background: var(--bg-soft);
  border-style: dashed;
}

.slot--filled {
  border-color: #bfdbfe;
}

.slot__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.slot__index {
  font-size: 12px;
  color: var(--muted);
}

.slot__remove {
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
  background: none;
  border: none;
}

.slot__remove:hover {
  color: var(--up);
}

.slot__name {
  font-size: 15px;
  font-weight: 600;
}

.slot__code {
  font-family: var(--font-num);
  font-size: 12px;
  color: var(--muted);
}

.slot__plus {
  font-size: 22px;
  line-height: 1;
}

.picker {
  padding: 16px;
  margin-bottom: 16px;
}

.picker__form {
  display: flex;
  gap: 10px;
}

.picker__input {
  flex: 1;
  padding: 9px 12px;
  font-family: inherit;
  font-size: 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
}

.picker__list {
  padding: 0;
  margin: 12px 0 0;
  list-style: none;
}

.picker__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 10px 8px;
  text-align: left;
  cursor: pointer;
  background: none;
  border: none;
  border-bottom: 1px solid var(--line-soft);
}

.picker__item:hover {
  background: var(--bg-soft);
}

.picker__name {
  font-size: 14px;
}

.picker__meta {
  font-size: 12px;
  color: var(--muted);
}

.empty {
  padding: 56px 24px;
  text-align: center;
  background: var(--bg-soft);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

.empty h2 {
  margin: 0 0 8px;
  font-size: 18px;
}

.empty p {
  margin: 0;
  color: var(--muted);
}

.hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--muted);
}

.hint--error {
  color: var(--up);
}

.table-wrap {
  padding: 0;
  margin-bottom: 16px;
  overflow-x: auto;
}

.period__title {
  padding: 14px 16px 0;
  margin: 0;
  font-size: 15px;
}

.period__hint {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 400;
  color: var(--muted);
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
}

.table th,
.table td {
  padding: 10px 14px;
  text-align: left;
  border-bottom: 1px solid var(--line-soft);
}

.table thead th {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
  background: var(--bg-soft);
}

.table__label {
  width: 190px;
  font-weight: 500;
  color: var(--muted);
}

.table__fund {
  color: var(--ink);
  text-decoration: none;
}

.table__fund:hover {
  color: var(--brand);
}

.table__code {
  font-family: var(--font-num);
  font-size: 11.5px;
  font-weight: 400;
  color: var(--muted-2);
}

.table__hint {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  font-weight: 400;
  color: var(--muted-2);
}

.is-missing {
  color: var(--muted-2);
}

.note {
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--muted);
}

@media (max-width: 720px) {
  .slots {
    grid-template-columns: 1fr;
  }

  .table__label {
    width: 120px;
  }
}
</style>
