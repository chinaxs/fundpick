<script setup lang="ts">
import type { TradeHistoryItem } from '@project/shared'
interface Filters {
  keyword: string
  kind: '' | 'buy' | 'sell'
  status: '' | TradeHistoryItem['status']
  dates: string[]
}
const filters = defineModel<Filters>({ required: true })
const emit = defineEmits<{ reset: [] }>()
const keyword = ref(filters.value.keyword)
watch(
  () => filters.value.keyword,
  (value) => {
    keyword.value = value
  },
)
function search() {
  filters.value.keyword = keyword.value.trim()
}
</script>
<template>
  <div class="history-filters">
    <form class="history-search" role="search" @submit.prevent="search">
      <el-input
        v-model="keyword"
        placeholder="搜索基金名称或代码"
        aria-label="基金名称或代码"
        clearable
        maxlength="100"
        @clear="search"
        ><template #append><el-button native-type="submit">搜索</el-button></template></el-input
      >
    </form>
    <el-select v-model="filters.kind" placeholder="全部方向" aria-label="交易方向"
      ><el-option label="全部方向" value="" /><el-option label="买入" value="buy" /><el-option
        label="卖出"
        value="sell"
    /></el-select>
    <el-select v-model="filters.status" placeholder="全部状态" aria-label="交易状态"
      ><el-option label="全部状态" value="" /><el-option label="待入账" value="pending" /><el-option
        label="已入账"
        value="confirmed" /><el-option label="已撤销" value="cancelled" /><el-option
        label="已作废"
        value="voided"
    /></el-select>
    <el-date-picker
      v-model="filters.dates"
      type="daterange"
      value-format="YYYY-MM-DD"
      format="YYYY-MM-DD"
      start-placeholder="下单开始日期"
      end-placeholder="结束日期"
      aria-label="下单日期范围"
      :editable="false"
    />
    <el-button link type="primary" @click="emit('reset')">重置</el-button>
  </div>
</template>
<style scoped>
.history-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 18px 0;
}
.history-search {
  width: 260px;
}
.history-filters > .el-select {
  width: 115px;
}
.history-filters > :deep(.el-date-editor) {
  flex: 0 1 270px;
  width: 270px;
}
@media (max-width: 768px) {
  .history-search {
    width: 100%;
  }
  .history-filters > .el-select {
    flex: 1;
  }
  .history-filters > :deep(.el-date-editor) {
    flex-basis: 100%;
    width: 100%;
  }
}
</style>
