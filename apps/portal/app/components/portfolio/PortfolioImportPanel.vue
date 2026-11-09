<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'

import type { ImportResult, ImportRowInput } from '~/composables/usePortfolioTools'
import { portfolioToday } from '~/composables/usePortfolioTools'

/** 默认单笔持仓初始化；批量CSV按需展开，预览走dry_run。 */
const emit = defineEmits<{ imported: [] }>()
const { previewImport, commitImport } = usePortfolioTools()

const raw = ref('')
const rows = ref<ImportRowInput[]>([])
const parseErrors = ref<string[]>([])
const result = ref<ImportResult | null>(null)
const busy = ref(false)
const message = ref('')
const singleForm = ref<FormInstance>()
const singleMessage = ref('')
const singleFailed = ref(false)
const single = reactive({
  code: '',
  confirmed_on: portfolioToday(),
  shares: '',
  amount: '',
  platform: '',
})
const positive = /^(?:0*[1-9]\d*(?:\.\d+)?|0*\.\d*[1-9]\d*)$/
const singleRules: FormRules = {
  code: [{ required: true, pattern: /^\d{6}$/, message: '请填写6位基金代码', trigger: 'blur' }],
  confirmed_on: [{ required: true, message: '请选择持仓日期', trigger: 'change' }],
  shares: [
    { required: true, pattern: positive, message: '请填写大于0的持有份额', trigger: 'blur' },
  ],
  amount: [
    { required: true, pattern: positive, message: '请填写大于0的持仓成本', trigger: 'blur' },
  ],
}

async function saveSingle() {
  if (busy.value || !(await singleForm.value?.validate().catch(() => false))) return
  busy.value = true
  singleMessage.value = ''
  singleFailed.value = false
  try {
    const created = await commitImport([
      { ...single, code: single.code.trim(), platform: single.platform.trim() || null },
    ])
    if (created.errors.length || created.created !== 1) {
      singleFailed.value = true
      singleMessage.value =
        created.errors.map((item) => item.reason).join('；') || '添加失败，请核对填写内容'
      return
    }
    singleMessage.value = '持仓已添加，可以继续记录买卖'
    single.code = ''
    single.shares = ''
    single.amount = ''
    singleForm.value?.clearValidate()
    emit('imported')
  } catch (error) {
    singleFailed.value = true
    singleMessage.value = tradeError(error)
  } finally {
    busy.value = false
  }
}

const canCommit = computed(() => result.value?.dry_run === true && result.value.imported.length > 0)

function parse() {
  parseErrors.value = []
  rows.value = []
  result.value = null
  message.value = ''
  const lines = raw.value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  if (!lines.length) {
    message.value = '请先粘贴数据。'
    return
  }
  lines.forEach((line, index) => {
    if (index === 0 && /代码|code/i.test(line)) return // 表头
    const parts = line.split(/[,，\t]/).map((part) => part.trim())
    const [code, confirmedOn, shares, amount, nav, platform, note] = parts
    if (!code || !/^\d{6}$/.test(code)) {
      parseErrors.value.push(`第 ${index + 1} 行：基金代码应为 6 位数字`)
      return
    }
    if (!confirmedOn || !/^\d{4}-\d{2}-\d{2}$/.test(confirmedOn)) {
      parseErrors.value.push(`第 ${index + 1} 行：日期格式应为 YYYY-MM-DD`)
      return
    }
    const numbers = [shares, amount, nav].filter((value) => value && value !== '-').length
    if (numbers < 2) {
      parseErrors.value.push(`第 ${index + 1} 行：份额、金额、净值至少填两项`)
      return
    }
    rows.value.push({
      code,
      confirmed_on: confirmedOn,
      shares: shares || null,
      amount: amount || null,
      nav: nav || null,
      platform: platform || null,
      note: note || null,
    })
  })
  if (!parseErrors.value.length) {
    message.value = `已解析 ${rows.value.length} 行，下一步点「校验」查看影响。`
  }
}

watch(
  raw,
  () => {
    rows.value = []
    result.value = null
    parseErrors.value = []
    message.value = ''
  },
  { flush: 'sync' },
)

async function preview() {
  if (!rows.value.length) parse()
  if (!rows.value.length || parseErrors.value.length) return
  busy.value = true
  message.value = ''
  try {
    result.value = await previewImport(rows.value)
    message.value = result.value.errors.length
      ? '有部分行无法导入，见下方说明。'
      : '校验通过，可以确认导入。'
  } catch (err) {
    message.value = err instanceof Error ? err.message : '校验失败'
  } finally {
    busy.value = false
  }
}

async function commit() {
  if (!rows.value.length || parseErrors.value.length || busy.value) return
  busy.value = true
  try {
    const created = await commitImport(rows.value)
    raw.value = ''
    rows.value = []
    result.value = null
    message.value = created.errors.length
      ? `已导入 ${created.created} 笔；${created.errors.map((item) => `第${item.index}行：${item.reason}`).join('；')}`
      : `已导入 ${created.created} 笔买入记录。`
    emit('imported')
  } catch (err) {
    message.value = err instanceof Error ? err.message : '导入失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="panel tools-panel">
    <h2 class="panel__title">添加已有持仓</h2>
    <p>填入开始记录时的份额与剩余成本，从该日期起计算收益。已有交易的基金请通过买卖记录调整。</p>
    <el-form
      ref="singleForm"
      class="tools-form"
      :model="single"
      :rules="singleRules"
      label-position="top"
      size="large"
      :disabled="busy"
      @submit.prevent="saveSingle"
    >
      <div class="tools-fields">
        <el-form-item label="基金代码" prop="code"
          ><el-input
            v-model="single.code"
            maxlength="6"
            inputmode="numeric"
            placeholder="输入6位代码"
            aria-label="基金代码"
        /></el-form-item>
        <el-form-item label="持仓日期" prop="confirmed_on"
          ><el-date-picker
            v-model="single.confirmed_on"
            type="date"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            :clearable="false"
            :teleported="false"
            aria-label="持仓日期"
        /></el-form-item>
        <el-form-item label="持有份额" prop="shares"
          ><el-input
            v-model="single.shares"
            inputmode="decimal"
            placeholder="平台显示的持有份额"
            aria-label="持有份额"
            ><template #suffix>份</template></el-input
          ></el-form-item
        >
        <el-form-item label="持仓成本" prop="amount"
          ><el-input
            v-model="single.amount"
            inputmode="decimal"
            placeholder="剩余成本，非当前市值"
            aria-label="持仓成本"
            ><template #suffix>元</template></el-input
          ></el-form-item
        >
      </div>
      <details class="tools-options">
        <summary>交易平台（选填）</summary>
        <el-form-item label="交易平台"
          ><el-input
            v-model="single.platform"
            maxlength="80"
            placeholder="如：支付宝、天天基金"
            aria-label="交易平台"
        /></el-form-item>
      </details>
      <el-button type="primary" class="tools-submit" native-type="submit" :loading="busy"
        >保存持仓</el-button
      >
    </el-form>
    <el-alert
      v-if="singleMessage"
      class="tools-message"
      :title="singleMessage"
      :type="singleFailed ? 'error' : 'success'"
      :closable="false"
      role="status"
    />
    <details class="tools-options">
      <summary>多只基金？批量导入</summary>
      <p class="panel__hint">
        每行一笔买入：<code>代码,日期,份额,金额,净值,平台,备注</code>，份额/金额/净值填两项即可。
        仅用于该基金还没有任何记录的情况，避免历史被记两遍。
      </p>
      <textarea
        v-model="raw"
        :disabled="busy"
        class="panel__input"
        rows="6"
        placeholder="000003,2026-03-12,1000,1200,1.2,支付宝,首次建仓"
      />
      <div class="panel__actions">
        <button type="button" class="btn btn--ghost" :disabled="busy" @click="preview">
          校验预览
        </button>
        <button v-if="canCommit" type="button" class="btn" :disabled="busy" @click="commit">
          确认导入
        </button>
      </div>

      <p v-if="message" class="panel__msg" role="status">{{ message }}</p>
      <ul v-if="parseErrors.length" class="errors">
        <li v-for="error in parseErrors" :key="error">{{ error }}</li>
      </ul>

      <template v-if="result">
        <h3 class="panel__sub">将导入 {{ result.imported.length }} 笔</h3>
        <div class="tools-table-wrap">
          <table v-if="result.imported.length" class="table">
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>确认日</th>
                <th>份额</th>
                <th>金额</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in result.imported" :key="index">
                <td>{{ row.code }}</td>
                <td>{{ row.name }}</td>
                <td>{{ row.confirmed_on }}</td>
                <td>{{ row.shares }}</td>
                <td>{{ row.amount }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <ul v-if="result.errors.length" class="errors">
          <li v-for="error in result.errors" :key="`${error.index}-${error.reason}`">
            第 {{ error.index }} 行（{{ error.code ?? '—' }}）：{{ error.reason }}
          </li>
        </ul>
      </template>
    </details>
  </section>
</template>

<style scoped>
.panel {
  padding: 20px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.panel__title {
  margin: 0 0 6px;
  font-size: 17px;
}

.panel__hint {
  margin: 0 0 12px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--muted);
}

.panel__input {
  width: 100%;
  padding: 10px 12px;
  font-family: var(--font-num);
  font-size: 12.5px;
  line-height: 1.7;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
}

.panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.panel__msg {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--ink-2);
}

.panel__sub {
  margin: 16px 0 8px;
  font-size: 14px;
}

.btn {
  padding: 8px 18px;
  font-size: 14px;
  color: #fff;
  cursor: pointer;
  background: var(--brand);
  border: none;
  border-radius: 999px;
}

.btn--ghost {
  color: var(--ink-2);
  background: none;
  border: 1px solid var(--line);
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.errors {
  padding-left: 18px;
  margin: 10px 0 0;
  font-size: 12.5px;
  color: var(--up);
}

.table {
  width: 100%;
  font-size: 12.5px;
  border-collapse: collapse;
}

.table th,
.table td {
  padding: 6px 10px;
  text-align: left;
  border-bottom: 1px solid var(--line-soft);
}

code {
  padding: 1px 4px;
  font-size: 11.5px;
  background: var(--bg-soft);
  border-radius: 4px;
}
</style>
