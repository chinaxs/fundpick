<script setup lang="ts">
import type { PageResult, TradeHistoryItem } from '@project/shared'
defineProps<{
  data: PageResult<TradeHistoryItem> | null | undefined
  pending: boolean
  failed: boolean
  page: number
  pageSize: number
  busy: boolean
}>()
const emit = defineEmits<{
  page: [value: number]
  pageSize: [value: number]
  retry: []
  cancel: [id: number]
  void: [item: TradeHistoryItem]
  remove: [item: TradeHistoryItem]
}>()
</script>
<template>
  <section class="p-card history-card">
    <div class="p-head">
      <h2>交易记录</h2>
      <span class="p-note">{{ data?.total ?? 0 }} 条</span>
    </div>
    <slot />
    <div v-if="failed" class="p-error" role="alert">
      交易记录加载失败。<el-button link type="primary" @click="emit('retry')">重试</el-button>
    </div>
    <div v-else v-loading="pending" class="history-results" :aria-busy="pending">
      <div
        v-if="data?.items.length"
        class="p-table-wrap"
        tabindex="0"
        aria-label="交易记录，可横向滚动"
      >
        <table class="data-table">
          <thead>
            <tr>
              <th>基金</th>
              <th>方向 / 下单时间</th>
              <th>金额 / 份额</th>
              <th>净值 / 日期</th>
              <th>交易费用</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <PortfolioHistoryRow
              v-for="item in data.items"
              :key="`${item.record_type}:${item.id}`"
              :item="item"
              :busy="busy || pending"
              @cancel="emit('cancel', $event)"
              @void="emit('void', $event)"
              @remove="emit('remove', $event)"
            />
          </tbody>
        </table>
      </div>
      <el-empty
        v-else-if="!pending"
        description="没有符合条件的记录，可调整搜索或筛选条件"
        :image-size="60"
      />
      <p v-else class="p-empty" role="status">正在加载交易记录…</p>
    </div>
    <el-pagination
      v-if="!failed"
      class="history-pagination"
      background
      :current-page="page"
      :page-size="pageSize"
      :total="data?.total ?? 0"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      :disabled="pending || busy"
      @update:current-page="emit('page', $event)"
      @update:page-size="emit('pageSize', $event)"
    />
  </section>
</template>
