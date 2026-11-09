<script setup lang="ts">
import type { ReceiptForm } from '~/composables/useTradeForm'
const form = defineModel<ReceiptForm>({ required: true })
defineProps<{ needsPrice: boolean; needsDate: boolean; platformFixed: boolean }>()
const platforms = ['支付宝', '天天基金', '微信理财通']
function suggestions(query: string, done: (items: { value: string }[]) => void) {
  done(platforms.filter((item) => item.includes(query)).map((value) => ({ value })))
}
</script>
<template>
  <div class="entry-receipt">
    <div class="entry-section-title">成交结果 <span>照平台显示填写</span></div>
    <el-form-item label="交易平台" prop="platform"
      ><el-autocomplete
        v-model="form.platform"
        :fetch-suggestions="suggestions"
        :readonly="platformFixed"
        maxlength="80"
        placeholder="输入或选择购买平台"
    /></el-form-item>
    <div class="entry-receipt-grid">
      <el-form-item v-if="form.kind === 'buy'" label="确认份额" prop="confirmed_shares"
        ><el-input v-model="form.confirmed_shares" inputmode="decimal" placeholder="实际买到的份额"
          ><template #suffix>份</template></el-input
        ></el-form-item
      >
      <el-form-item v-else label="实际到账" prop="received_amount"
        ><el-input v-model="form.received_amount" inputmode="decimal" placeholder="平台确认的金额"
          ><template #prefix>¥</template></el-input
        ></el-form-item
      >
      <el-form-item label="手续费" prop="fee"
        ><el-input v-model="form.fee" inputmode="decimal" placeholder="实际费用"
          ><template #append
            ><el-button native-type="button" @click="form.fee = '0'">无费用</el-button></template
          ></el-input
        ></el-form-item
      >
      <el-form-item v-if="needsDate" label="平台显示的净值日期" prop="confirmed_on"
        ><el-date-picker
          v-model="form.confirmed_on"
          type="date"
          value-format="YYYY-MM-DD"
          format="YYYY-MM-DD"
          :clearable="false"
          placeholder="按平台显示填写"
          :teleported="false"
      /></el-form-item>
      <el-form-item v-if="needsPrice" label="成交净值" prop="nav"
        ><el-input v-model="form.nav" inputmode="decimal" placeholder="按平台显示填写"
      /></el-form-item>
    </div>
    <el-collapse class="entry-adjustments"
      ><el-collapse-item title="平台日期或净值不同？" name="adjust"
        ><el-checkbox v-model="form.adjusted"
          >改用平台显示的日期与净值</el-checkbox
        ></el-collapse-item
      ></el-collapse
    >
  </div>
</template>
