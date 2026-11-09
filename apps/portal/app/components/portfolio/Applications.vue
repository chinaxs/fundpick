<script setup lang="ts">
import type { ApplicationRead, TradeSeed } from '@project/shared'
defineProps<{ items: ApplicationRead[]; busy: boolean }>()
const emit = defineEmits<{ record: [seed: TradeSeed]; cancel: [id: number] }>()
function timeLabel(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}
function record(item: ApplicationRead) {
  emit('record', {
    kind: item.kind,
    code: item.code,
    name: item.name,
    platform: item.platform,
    submitted_at: item.submitted_at,
    confirmed_on: item.expected_nav_on ?? undefined,
    pricing_rule: item.pricing_rule,
    amount: item.amount ? Number(item.amount) : undefined,
    requested_shares: item.shares ?? undefined,
    application_id: item.id,
  })
}
</script>
<template>
  <section v-if="items.length" class="p-card applications">
    <h2>待入账 · {{ items.length }} 笔</h2>
    <p class="p-note">
      到确认日且净值、费用齐全后，后台自动入账；无需保持页面打开。暂缺信息会定期重试。
    </p>
    <article v-for="item in items" :key="item.id" class="legacy-review__row">
      <div>
        <div style="padding: 0">
          <small>{{ item.requires_review ? '需要核对' : '自动等待入账' }}</small>
          <strong>{{ item.name }} · {{ item.kind === 'buy' ? '买入' : '卖出' }}</strong
          ><small
            >{{ item.platform || '平台未填写' }} · 下单
            {{ item.submitted_at.replace('T', ' ').replace('+08:00', '') }}</small
          >
        </div>
        <p style="padding: 0">
          {{ item.expected_nav_on ? `按 ${item.expected_nav_on} 净值` : '价格待平台确认' }} ·
          {{ item.amount ? `金额 ¥ ${item.amount}` : `份额 ${item.shares}` }}
        </p>
      </div>
      <p v-if="item.processing_message" class="p-note">
        {{ item.processing_message
        }}<small v-if="item.last_attempt_at"
          >最近核对 {{ timeLabel(item.last_attempt_at)
          }}<template v-if="item.next_retry_at">
            · 下次检查 {{ timeLabel(item.next_retry_at) }}</template
          ></small
        >
      </p>
      <div class="p-actions">
        <button type="button" class="p-link" :disabled="busy" @click="emit('cancel', item.id)">
          撤销记录</button
        ><button v-if="item.requires_review" type="button" class="p-link" @click="record(item)">
          处理异常
        </button>
      </div>
    </article>
  </section>
</template>
