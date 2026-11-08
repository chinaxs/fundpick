<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import type { HoldingRead } from '@project/shared'
import { portfolioToday, type FlowPayload, type FlowRecord } from '~/composables/usePortfolioTools'

const props = withDefaults(
  defineProps<{
    initialKind?: 'dividend' | 'reinvest' | 'split' | 'convert_out' | 'convert_in'
    holdings?: HoldingRead[]
  }>(),
  { initialKind: 'dividend', holdings: () => [] },
)
const emit = defineEmits<{ changed: [] }>()
const { listFlows, addFlow, removeFlow } = usePortfolioTools()
const flows = ref<FlowRecord[]>([])
const loading = ref(false)
const loadFailed = ref(false)
const submitting = ref(false)
const message = ref('')
const failed = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  kind: props.initialKind,
  code: '',
  effective_on: portfolioToday(),
  cash_amount: '',
  shares_delta: '',
  nav: '',
  ratio: '',
  target_code: '',
  target_shares: '',
  target_nav: '',
  target_cash_amount: '',
  platform: '',
  note: '',
})
function newRequestKey() {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `flow-${Date.now()}-${Math.random().toString(16).slice(2)}`
}
const requestKey = ref(newRequestKey())
const isConvert = computed(() => form.kind === 'convert_in' || form.kind === 'convert_out')
const isDividend = computed(() => form.kind === 'dividend' || form.kind === 'reinvest')
const selfSide = computed(() => (form.kind === 'convert_in' ? '转入' : '转出'))
const peerSide = computed(() => (form.kind === 'convert_in' ? '转出' : '转入'))
const heading = computed(() =>
  isDividend.value ? '记录分红' : isConvert.value ? '基金转换' : '份额拆分 / 合并',
)
const held = computed(() => props.holdings.filter((item) => item.shares > 0))
const positive = (label: string) => ({
  pattern: /^(?:0*[1-9]\d*(?:\.\d+)?|0*\.\d*[1-9]\d*)$/,
  message: `请填写大于0的${label}`,
  trigger: 'blur',
})
const rules = computed<FormRules>(() => ({
  code: [
    { required: true, pattern: /^\d{6}$/, message: '请选择基金或输入6位代码', trigger: 'change' },
  ],
  effective_on: [{ required: true, message: '请选择实际生效日期', trigger: 'change' }],
  cash_amount: [{ required: true, message: '请填写金额', trigger: 'blur' }, positive('金额')],
  shares_delta: [{ required: true, message: '请填写份额', trigger: 'blur' }, positive('份额')],
  ratio: [{ required: true, message: '请填写拆分比例', trigger: 'blur' }, positive('比例')],
  target_code: [
    { required: true, pattern: /^\d{6}$/, message: '请填写另一只基金的6位代码', trigger: 'blur' },
  ],
  target_shares: [{ required: true, message: '请填写份额', trigger: 'blur' }, positive('份额')],
  target_cash_amount: [
    { required: true, message: '请填写实际金额', trigger: 'blur' },
    positive('金额'),
  ],
}))
watch(
  () => form.kind,
  () => {
    formRef.value?.clearValidate()
    message.value = ''
  },
)

async function load() {
  loading.value = true
  loadFailed.value = false
  try {
    flows.value = await listFlows()
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}
function payload(): FlowPayload {
  const shares = form.shares_delta ? Number(form.shares_delta) : null
  return {
    code: form.code.trim(),
    kind: form.kind,
    effective_on: form.effective_on,
    cash_amount: form.kind === 'split' ? null : Number(form.cash_amount),
    shares_delta:
      form.kind === 'dividend' || form.kind === 'split'
        ? null
        : form.kind === 'convert_out'
          ? -Math.abs(shares ?? 0)
          : shares,
    nav: form.nav && form.kind !== 'dividend' && form.kind !== 'split' ? Number(form.nav) : null,
    ratio: form.kind === 'split' ? Number(form.ratio) : null,
    target_code: isConvert.value ? form.target_code.trim() : null,
    target_shares: isConvert.value ? Number(form.target_shares) : null,
    target_nav: isConvert.value && form.target_nav ? Number(form.target_nav) : null,
    target_cash_amount: isConvert.value ? Number(form.target_cash_amount) : null,
    platform: form.kind === 'split' ? null : form.platform.trim() || null,
    request_key: requestKey.value,
    note: form.note.trim() || null,
  }
}
async function submit() {
  if (submitting.value || !(await formRef.value?.validate().catch(() => false))) return
  submitting.value = true
  message.value = ''
  failed.value = false
  try {
    await addFlow(payload())
    message.value = '已记录，持仓和收益已更新'
    form.note = ''
    form.cash_amount = ''
    form.shares_delta = ''
    form.nav = ''
    form.target_shares = ''
    form.target_nav = ''
    form.target_cash_amount = ''
    requestKey.value = newRequestKey()
    await load()
    emit('changed')
    formRef.value?.clearValidate()
  } catch (error) {
    failed.value = true
    message.value = tradeError(error)
  } finally {
    submitting.value = false
  }
}
async function remove(id: number) {
  submitting.value = true
  try {
    await removeFlow(id)
    await load()
    emit('changed')
    failed.value = false
    message.value = '记录已删除，持仓已更新'
  } catch (error) {
    failed.value = true
    message.value = tradeError(error)
  } finally {
    submitting.value = false
  }
}
onMounted(() => void load())
</script>

<template>
  <section class="tools-panel flow-panel">
    <h2>{{ heading }}</h2>
    <p v-if="isDividend">按实际收到的分红记录，保存后自动更新持仓与收益。</p>
    <p v-else-if="isConvert">按实际结果填写两只基金的份额和金额，金额差会计入转换费用。</p>
    <p v-else>例如1份变2份填2；2份合为1份填0.5。</p>

    <el-radio-group v-if="isDividend" v-model="form.kind" aria-label="分红方式">
      <el-radio-button value="dividend">现金分红</el-radio-button>
      <el-radio-button value="reinvest">红利再投</el-radio-button>
    </el-radio-group>

    <el-form
      ref="formRef"
      class="tools-form"
      :model="form"
      :rules="rules"
      label-position="top"
      size="large"
      :disabled="submitting"
      @submit.prevent="submit"
    >
      <div class="tools-fields">
        <el-form-item :label="isConvert ? `${selfSide}基金` : '基金'" prop="code">
          <el-select
            v-model="form.code"
            filterable
            allow-create
            default-first-option
            placeholder="选择持仓或输入6位代码"
            aria-label="基金代码"
          >
            <el-option
              v-for="fund in held"
              :key="fund.code"
              :value="fund.code"
              :label="`${fund.name} · ${fund.code}`"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="生效日期" prop="effective_on">
          <el-date-picker
            v-model="form.effective_on"
            type="date"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            :clearable="false"
            :teleported="false"
            aria-label="生效日期"
          />
        </el-form-item>
      </div>
      <el-form-item v-if="form.kind === 'dividend'" label="分红金额" prop="cash_amount">
        <el-input
          v-model="form.cash_amount"
          inputmode="decimal"
          placeholder="实际收到的金额"
          aria-label="分红金额"
          ><template #suffix>元</template></el-input
        >
      </el-form-item>
      <div v-if="form.kind === 'reinvest'" class="tools-fields">
        <el-form-item label="再投金额" prop="cash_amount"
          ><el-input
            v-model="form.cash_amount"
            inputmode="decimal"
            placeholder="用于再投的分红"
            aria-label="再投金额"
            ><template #suffix>元</template></el-input
          ></el-form-item
        >
        <el-form-item label="再投份额" prop="shares_delta"
          ><el-input
            v-model="form.shares_delta"
            inputmode="decimal"
            placeholder="实际增加的份额"
            aria-label="再投份额"
            ><template #suffix>份</template></el-input
          ></el-form-item
        >
      </div>
      <el-form-item v-if="form.kind === 'split'" label="拆分比例" prop="ratio"
        ><el-input
          v-model="form.ratio"
          inputmode="decimal"
          placeholder="例如：2"
          aria-label="拆分比例"
      /></el-form-item>
      <template v-if="isConvert">
        <div class="tools-fields">
          <el-form-item :label="`${selfSide}份额`" prop="shares_delta"
            ><el-input
              v-model="form.shares_delta"
              inputmode="decimal"
              :aria-label="`${selfSide}份额`"
              ><template #suffix>份</template></el-input
            ></el-form-item
          >
          <el-form-item :label="`${selfSide}金额`" prop="cash_amount"
            ><el-input
              v-model="form.cash_amount"
              inputmode="decimal"
              :aria-label="`${selfSide}金额`"
              ><template #suffix>元</template></el-input
            ></el-form-item
          >
        </div>
        <p class="tools-transfer-title">↓ {{ peerSide }}到另一只基金</p>
        <el-form-item :label="`${peerSide}基金`" prop="target_code"
          ><el-input
            v-model="form.target_code"
            maxlength="6"
            inputmode="numeric"
            placeholder="输入6位基金代码"
            :aria-label="`${peerSide}基金代码`"
        /></el-form-item>
        <div class="tools-fields">
          <el-form-item :label="`${peerSide}份额`" prop="target_shares"
            ><el-input
              v-model="form.target_shares"
              inputmode="decimal"
              :aria-label="`${peerSide}份额`"
              ><template #suffix>份</template></el-input
            ></el-form-item
          >
          <el-form-item :label="`${peerSide}金额`" prop="target_cash_amount"
            ><el-input
              v-model="form.target_cash_amount"
              inputmode="decimal"
              :aria-label="`${peerSide}金额`"
              ><template #suffix>元</template></el-input
            ></el-form-item
          >
        </div>
      </template>
      <details class="tools-options">
        <summary>平台与备注（选填）</summary>
        <el-form-item v-if="form.kind !== 'split'" label="交易平台"
          ><el-input
            v-model="form.platform"
            maxlength="80"
            placeholder="单平台自动识别；多平台时请填写"
            aria-label="交易平台"
        /></el-form-item>
        <el-form-item label="备注"
          ><el-input v-model="form.note" maxlength="200" placeholder="选填" aria-label="备注"
        /></el-form-item>
      </details>
      <el-button class="tools-submit" type="primary" native-type="submit" :loading="submitting"
        >保存记录</el-button
      >
    </el-form>
    <el-alert
      v-if="message"
      class="tools-message"
      :title="message"
      :type="failed ? 'error' : 'success'"
      :closable="false"
      show-icon
      role="status"
    />

    <details class="tools-records">
      <summary>查看补充记录{{ flows.length ? `（${flows.length}）` : '' }}</summary>
      <p v-if="loading">加载中…</p>
      <el-button v-else-if="loadFailed" link @click="load">加载失败，点击重试</el-button>
      <p v-else-if="!flows.length">暂无补充记录</p>
      <div v-else class="tools-table-wrap">
        <table class="tools-table">
          <thead>
            <tr>
              <th>日期 / 基金</th>
              <th>类型</th>
              <th>金额</th>
              <th>份额变化</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="flow in flows" :key="flow.id">
              <td>
                {{ flow.effective_on
                }}<small
                  >{{ flow.fund_name }} · {{ flow.code
                  }}{{ flow.platform ? ` · ${flow.platform}` : '' }}</small
                >
              </td>
              <td>
                {{ flow.kind_label
                }}<small v-if="flow.target_code"
                  >{{ flow.kind === 'convert_out' ? '转入' : '转出' }} {{ flow.target_code }}</small
                >
              </td>
              <td>
                {{ flow.cash_amount ?? '—'
                }}<small v-if="flow.net_amount != null && flow.net_amount !== flow.cash_amount"
                  >实际转入 {{ flow.net_amount }}</small
                >
              </td>
              <td>{{ flow.shares_delta ?? (flow.ratio ? `×${flow.ratio}` : '—') }}</td>
              <td>
                <el-button link type="danger" :disabled="submitting" @click="remove(flow.id)"
                  >删除</el-button
                >
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  </section>
</template>
