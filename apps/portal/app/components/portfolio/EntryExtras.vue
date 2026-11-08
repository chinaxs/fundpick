<script setup lang="ts">
import type { ReceiptForm } from '~/composables/useTradeForm'
const form = defineModel<ReceiptForm>({ required: true })
defineProps<{ canDefer: boolean }>()
const open = ref<string[]>([])
</script>
<template>
  <el-collapse v-model="open" class="entry-more"
    ><el-collapse-item
      name="more"
      :title="
        form.stage === 'pending' ? '平台与备注（选填，选择平台可匹配优惠费率）' : '更多信息（选填）'
      "
    >
      <el-form-item v-if="form.stage === 'pending'" label="交易平台"
        ><el-input v-model="form.platform" maxlength="80" placeholder="如：支付宝、天天基金"
      /></el-form-item>
      <template v-else
        ><el-form-item label="平台确认日期"
          ><el-date-picker
            v-model="form.settled_on"
            type="date"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            placeholder="不知道可留空"
            :teleported="false" /></el-form-item
        ><el-form-item label="回执编号"
          ><el-input v-model="form.receipt_ref" maxlength="100" placeholder="选填" /></el-form-item
      ></template>
      <el-form-item label="备注"
        ><el-input v-model="form.note" maxlength="200" placeholder="留个记录，方便以后复盘"
      /></el-form-item>
      <el-button
        v-if="form.stage === 'pending'"
        link
        type="primary"
        native-type="button"
        class="entry-receipt-link"
        @click="form.stage = 'receipt'"
        >成交数据异常？按平台信息核对</el-button
      >
    </el-collapse-item></el-collapse
  >
  <el-button
    v-if="form.stage === 'receipt' && canDefer"
    link
    native-type="button"
    class="entry-receipt-link"
    @click="form.stage = 'pending'"
    >交给系统自动计算</el-button
  >
</template>
