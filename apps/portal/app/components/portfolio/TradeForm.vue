<script setup lang="ts">
import type { FormInstance, InputInstance } from 'element-plus'
import type { TradeSeed } from '@project/shared'
const props = defineProps<{ seed: TradeSeed }>()
const emit = defineEmits<{ completed: [message?: string]; close: [] }>()
const { form, quote, timing, timingError, timingBusy, busy, error, save, confirm, edit } =
  useTradeForm(props.seed, (message) => emit('completed', message))
const { editingTime, rules, timeLabel } = useTradeEntry(form)
const formRef = ref<FormInstance>()
const amountInput = ref<InputInstance>()
const amounts = [100, 500, 1000, 5000]
watch(
  () => [form.amount, form.shares],
  () => formRef.value?.clearValidate(['amount', 'shares']),
)
async function submit() {
  if (busy.value) return
  if (await formRef.value?.validate().catch(() => false)) await save()
}
</script>
<template>
  <el-dialog
    :model-value="true"
    class="trade-dialog"
    width="460px"
    align-center
    destroy-on-close
    :close-on-click-modal="false"
    :close-on-press-escape="!busy"
    :show-close="!busy"
    @opened="amountInput?.focus()"
    @update:model-value="!busy && emit('close')"
  >
    <template #header
      ><div class="trade-title">
        <span>{{ form.kind === 'buy' ? '记一笔买入' : '记一笔卖出' }}</span
        ><span class="trade-title__hint">{{ quote ? '核对差异' : '轻松记账' }}</span>
      </div></template
    >
    <div class="trade-flow trade-entry">
      <template v-if="!quote">
        <div v-if="seed.code" class="entry-fund">
          <span class="entry-fund__icon" aria-hidden="true">基</span>
          <div class="entry-fund__name">
            <strong>{{ seed.name ?? '基金' }}</strong
            ><span>{{ seed.code }} <HoldingBadge :code="seed.code" /></span>
          </div>
        </div>
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          size="large"
          :show-message="true"
          :disabled="busy"
          @submit.prevent="submit"
        >
          <el-form-item v-if="!seed.code" label="基金代码" prop="code"
            ><el-input
              v-model="form.code"
              maxlength="6"
              inputmode="numeric"
              placeholder="输入6位基金代码"
          /></el-form-item>
          <el-form-item
            :label="form.kind === 'buy' ? '买入金额' : '卖出份额'"
            :prop="form.kind === 'buy' ? 'amount' : 'shares'"
            class="entry-amount"
          >
            <el-input
              v-if="form.kind === 'buy'"
              ref="amountInput"
              v-model="form.amount"
              inputmode="decimal"
              placeholder="0.00"
              aria-label="买入金额"
              autocomplete="off"
              ><template #prefix>¥</template><template #suffix>元</template></el-input
            >
            <el-input
              v-else
              ref="amountInput"
              v-model="form.shares"
              inputmode="decimal"
              placeholder="0.0000"
              aria-label="卖出份额"
              autocomplete="off"
              ><template #suffix>份</template></el-input
            >
          </el-form-item>
          <div v-if="form.kind === 'buy'" class="amount-shortcuts" aria-label="常用金额">
            <el-button
              v-for="amount in amounts"
              :key="amount"
              :class="{ 'is-chosen': form.amount === String(amount) }"
              native-type="button"
              @click="form.amount = String(amount)"
              >{{ amount.toLocaleString('zh-CN') }}</el-button
            >
          </div>
          <div class="entry-time">
            <div class="entry-time__text">
              <svg viewBox="0 0 20 20" aria-hidden="true">
                <circle cx="10" cy="10" r="7" />
                <path d="M10 6v4l3 2" /></svg
              ><span>{{ timeLabel }} <small>北京时间</small></span>
            </div>
            <el-button
              v-if="!seed.application_id"
              link
              type="primary"
              native-type="button"
              :aria-expanded="editingTime"
              @click="editingTime = !editingTime"
              >{{ editingTime ? '收起' : '修改' }}</el-button
            >
          </div>
          <el-form-item v-if="editingTime" prop="submitted_at" class="entry-time-picker"
            ><el-date-picker
              v-model="form.submitted_at"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ss"
              format="YYYY-MM-DD HH:mm:ss"
              placeholder="选择实际下单时间"
              :clearable="false"
              :editable="false"
              popper-class="trade-date-popper"
              :teleported="false"
              aria-label="实际下单时间"
          /></el-form-item>
          <p class="entry-timing" role="status">
            <span v-if="timingBusy">正在核对日期…</span
            ><span v-else-if="timingError">{{ timingError }}</span
            ><span v-else-if="timing?.expected_nav_on"
              >按 {{ timing.expected_nav_on }} 净值记录<span v-if="!timing.official_nav"
                >，净值公布后自动计算</span
              ></span
            ><span v-else>自动查询净值和交易费用</span>
          </p>
          <PortfolioReceiptFields
            v-if="form.stage === 'receipt'"
            v-model="form"
            :needs-price="form.nav_mode === 'manual'"
            :needs-date="form.adjusted || timing?.pricing_rule === 'platform'"
            :platform-fixed="!!seed.application_id && !!seed.platform"
          />
          <PortfolioEntryExtras
            v-model="form"
            :can-defer="!seed.application_id && !seed.legacy_position_id"
          />
          <el-alert
            v-if="error"
            :title="error"
            type="error"
            :closable="false"
            show-icon
            role="alert"
          />
          <div class="entry-submit">
            <el-button type="primary" native-type="submit" :loading="busy">{{
              form.stage === 'pending' ? '自动计算并保存' : '保存成交结果'
            }}</el-button>
          </div>
        </el-form>
      </template>
      <template v-else
        ><PortfolioTradePreview :quote="quote" /><el-alert
          v-for="warning in quote.warnings.filter(
            (item) => item.includes('差异') || item.includes('不一致'),
          )"
          :key="warning"
          :title="warning"
          type="warning"
          :closable="false"
          show-icon
        /><el-alert v-if="error" :title="error" type="error" :closable="false" />
        <div class="entry-confirm">
          <el-button :disabled="busy" @click="edit">返回修改</el-button
          ><el-button type="primary" :loading="busy" @click="confirm">已核对，保存</el-button>
        </div></template
      >
      <p class="entry-footnote">净值与手续费自动查询；自动计算结果可按平台成交结果校准。</p>
    </div>
  </el-dialog>
</template>
<style src="~/assets/css/trade-entry.css"></style>
