<script setup lang="ts">
import type { DashboardData } from '@project/shared'
import { FUND_SECTOR_MAP, fmtPct, toneOf } from '@project/shared'
const props = defineProps<{ data: DashboardData }>()
const typeItems = computed(() => props.data.type_distribution)
const riskItems = computed(() => props.data.risk_distribution)
const sectorItems = computed(() => props.data.sector_distribution)
const bucketItems = computed(() => props.data.return_buckets)
const bucketMax = computed(() => Math.max(1, ...bucketItems.value.map((i) => i.count)))
const riskColors: Record<string, string> = {
  low: 'var(--down)',
  mid_low: 'var(--brand)',
  mid: 'var(--muted)',
  mid_high: 'var(--up)',
  high: 'var(--up)',
}
function barWidth(count: number, items: { count: number }[]): string {
  const max = Math.max(1, ...items.map((i) => i.count))
  return `${(count / max) * 100}%`
}
function sectorLabel(key: string): string {
  return FUND_SECTOR_MAP[key as keyof typeof FUND_SECTOR_MAP] ?? key
}
</script>
<template>
  <!-- 分布 -->
  <div class="grid2">
    <section class="card block">
      <div class="block__head">
        <div>
          <h2 class="block__title">类型分布</h2>
          <p class="block__sub">按关注只数统计，右侧为区间平均收益</p>
        </div>
      </div>
      <div class="bars">
        <div v-for="item in typeItems" :key="item.key" class="bar">
          <span class="bar__label">{{ item.label }}</span>
          <span class="bar__track">
            <span class="bar__fill" :style="{ width: barWidth(item.count, typeItems) }" />
          </span>
          <span class="bar__value num">
            {{ item.count }}
            <small :class="toneOf(item.avg_return)">{{ fmtPct(item.avg_return) }}</small>
          </span>
        </div>
      </div>
    </section>

    <section class="card block">
      <div class="block__head">
        <div>
          <h2 class="block__title">风险分布</h2>
          <p class="block__sub">按基金类型推导，仅作参考</p>
        </div>
      </div>
      <div class="bars">
        <div v-for="item in riskItems" :key="item.key" class="bar">
          <span class="bar__label">{{ item.label }}</span>
          <span class="bar__track">
            <span
              class="bar__fill"
              :style="{
                width: barWidth(item.count, riskItems),
                background: riskColors[item.key] ?? 'var(--muted-2)',
              }"
            />
          </span>
          <span class="bar__value num">{{ item.count }}</span>
        </div>
        <p v-if="!riskItems.length" class="block__sub">暂无数据</p>
      </div>
    </section>

    <section class="card block">
      <div class="block__head">
        <div>
          <h2 class="block__title">板块分布</h2>
          <p class="block__sub">关注最多的 8 个主题板块</p>
        </div>
      </div>
      <div v-if="sectorItems.length" class="sectors">
        <NuxtLink
          v-for="item in sectorItems"
          :key="item.key"
          :to="{ path: '/funds', query: { sector: item.key } }"
          class="sector-tag"
        >
          <span>{{ sectorLabel(item.key) }}</span>
          <span class="num">{{ item.count }}</span>
        </NuxtLink>
      </div>
      <p v-else class="block__sub">关注的基金暂无明确主题板块</p>
    </section>

    <section class="card block">
      <div class="block__head">
        <div>
          <h2 class="block__title">收益分布</h2>
          <p class="block__sub">所选区间收益率的分布（基金只数）</p>
        </div>
      </div>
      <div class="histogram">
        <div v-for="item in bucketItems" :key="item.key" class="histogram__col">
          <span class="histogram__count num">{{ item.count }}</span>
          <span class="histogram__bar-wrap">
            <span
              class="histogram__bar"
              :class="{
                'histogram__bar--up':
                  item.key.startsWith('>') || item.key.startsWith('10') || item.key.startsWith('0'),
              }"
              :style="{ height: `${(item.count / bucketMax) * 100}%` }"
            />
          </span>
          <span class="histogram__label num">{{ item.key }}</span>
        </div>
      </div>
    </section>
  </div>
</template>
