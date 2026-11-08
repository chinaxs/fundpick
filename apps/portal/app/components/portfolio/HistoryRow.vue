<script setup lang="ts">
import type { TradeHistoryItem } from '@project/shared'
import { fmtPoint } from '@project/shared'
const props = defineProps<{ item: TradeHistoryItem; busy: boolean }>()
const emit = defineEmits<{
  cancel: [id: number]
  void: [item: TradeHistoryItem]
  remove: [item: TradeHistoryItem]
}>()
const labels = { pending: '待入账', confirmed: '已入账', cancelled: '已撤销', voided: '已作废' }
const tagType = computed(() =>
  props.item.status === 'pending'
    ? 'warning'
    : props.item.status === 'confirmed'
      ? 'success'
      : 'info',
)
</script>
<template>
  <tr
    :data-record-id="item.id"
    :data-record-type="item.record_type"
    :data-status="item.status"
    :class="{ 'trade-voided': item.status === 'voided' || item.status === 'cancelled' }"
  >
    <td class="history-fund">
      <NuxtLink :to="`/funds/${item.code}`">{{ item.name }}</NuxtLink
      ><small>{{ item.code }}{{ item.platform ? ` · ${item.platform}` : '' }}</small>
    </td>
    <td>
      <span>{{ item.kind === 'buy' ? '买入' : '卖出' }}</span
      ><small>{{
        item.submitted_at
          ? item.submitted_at.replace('T', ' ').replace('+08:00', '')
          : (item.created_at?.replace('T', ' ').slice(0, 19) ?? '—')
      }}</small
      ><small v-if="!item.submitted_at">旧记录按录入日期筛选</small>
    </td>
    <td class="num">
      {{
        item.kind === 'buy' ? `¥ ${fmtPoint(item.amount)}` : `${item.shares?.toFixed(4) ?? '—'} 份`
      }}<small v-if="item.record_type === 'transaction'"
        >{{ item.kind === 'buy' ? '确认份额' : '净到账' }}
        {{
          item.kind === 'buy' ? (item.shares?.toFixed(4) ?? '—') : `¥ ${fmtPoint(item.cash_amount)}`
        }}</small
      >
    </td>
    <td>
      <span class="num">{{ item.nav?.toFixed(6) ?? '—' }}</span
      ><small>{{ item.confirmed_on || item.expected_nav_on || '价格日期待核对' }}</small>
    </td>
    <td class="num">
      {{ item.fee == null ? '待计算' : `¥ ${fmtPoint(item.fee)}`
      }}<PortfolioCalculationBasis v-if="item.calculation_basis" :basis="item.calculation_basis" />
    </td>
    <td>
      <el-tag :type="tagType" size="small" effect="light">{{ labels[item.status] }}</el-tag
      ><small v-if="item.status === 'confirmed'">{{
        item.record_source === 'estimated'
          ? '公开净值与费率自动计算'
          : item.record_source === 'receipt'
            ? '按平台结果记录'
            : '旧版折算'
      }}</small
      ><small v-if="item.status === 'pending'">{{
        item.processing_message || '数据齐全后自动入账'
      }}</small
      ><small v-if="item.void_reason">{{ item.void_reason }}</small
      ><small v-if="item.note">备注：{{ item.note }}</small>
    </td>
    <td>
      <el-button
        v-if="item.can_cancel"
        link
        type="primary"
        size="small"
        :disabled="busy"
        @click="emit('cancel', item.id)"
        >撤销记录</el-button
      ><el-button
        v-if="item.can_delete"
        link
        type="danger"
        size="small"
        :disabled="busy"
        @click="emit('remove', item)"
        >删除</el-button
      ><el-dropdown v-if="item.can_void" trigger="click" @command="emit('void', item)"
        ><el-button link size="small" :disabled="busy">更多 ▾</el-button
        ><template #dropdown
          ><el-dropdown-menu
            ><el-dropdown-item command="void">记错了，作废记录</el-dropdown-item></el-dropdown-menu
          ></template
        ></el-dropdown
      ><span v-if="!item.can_cancel && !item.can_delete && !item.can_void" class="p-note">—</span>
    </td>
  </tr>
</template>
