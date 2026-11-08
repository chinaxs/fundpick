<script setup lang="ts">
import type { FilterOptions, FundQuery, FundSortBy } from '@project/shared'
import {
  FUND_PERIOD_MAP,
  FUND_TYPE_MAP,
  FUND_SECTOR_MAP,
  RISK_LEVEL_MAP,
  FUND_SORT_MAP,
} from '@project/shared'
const props = defineProps<{ state: FundQuery; filters: FilterOptions | null | undefined }>()
const keyword = defineModel<string>('keyword', { required: true })
const emit = defineEmits<{
  filter: [key: 'type' | 'sector' | 'risk_level', value?: string]
  period: [value: string]
  sort: [value: FundSortBy]
  direction: []
  search: []
  composition: [value: boolean]
  reset: []
  preset: [value: FundQuery]
}>()
const sectorsExpanded = ref(false)
function endComposition() {
  emit('composition', false)
  emit('search')
}
const sectors = computed(() =>
  [
    ...(props.filters?.sectors ??
      Object.entries(FUND_SECTOR_MAP).map(([value, label]) => ({ value, label, count: 0 }))),
  ].sort((a, b) => b.count - a.count),
)
const rows = computed(() => [
  {
    key: 'type' as const,
    label: '类型',
    options: props.filters?.types.length
      ? props.filters.types
      : Object.entries(FUND_TYPE_MAP).map(([value, label]) => ({ value, label })),
  },
  {
    key: 'sector' as const,
    label: '板块',
    options: sectorsExpanded.value ? sectors.value : sectors.value.slice(0, 8),
  },
  {
    key: 'risk_level' as const,
    label: '风险',
    options: (props.filters?.risk_levels.length
      ? props.filters.risk_levels
      : Object.entries(RISK_LEVEL_MAP).map(([value, label]) => ({ value, label }))
    ).map((item) => ({ ...item, label: item.label.replace(/风险$/, '') })),
  },
])
const periods = Object.entries(FUND_PERIOD_MAP).map(([value, label]) => ({ value, label }))
const sorts = Object.entries(FUND_SORT_MAP).map(([value, label]) => ({ value, label }))
const presets = [
  {
    label: '指数基金 · 看长期',
    query: { type: 'index', period: '3y', sort_by: 'return', sort_order: 'desc' },
  },
  {
    label: '债券基金 · 看回撤',
    query: { type: 'bond', period: '1y', sort_by: 'max_drawdown', sort_order: 'asc' },
  },
  {
    label: '股票基金 · 看夏普',
    query: { type: 'stock', period: '1y', sort_by: 'sharpe', sort_order: 'desc' },
  },
] satisfies { label: string; query: FundQuery }[]
</script>

<template>
  <section class="filters" aria-label="基金筛选条件">
    <form class="filters__search" role="search" @submit.prevent="emit('search')">
      <label class="sr-only" for="fund-keyword">搜索基金代码、名称、拼音或主题</label>
      <input
        id="fund-keyword"
        v-model="keyword"
        type="search"
        placeholder="输入代码、名称、拼音首字母或主题，多词用空格分隔"
        @compositionstart="emit('composition', true)"
        @compositionend="endComposition"
      />
      <button type="submit" class="btn">搜索基金</button>
    </form>
    <div class="filters__presets">
      <span>快速开始</span
      ><button
        v-for="preset in presets"
        :key="preset.label"
        type="button"
        @click="emit('preset', preset.query)"
      >
        {{ preset.label }} →
      </button>
    </div>
    <div v-for="row in rows" :key="row.key" class="filters__row">
      <span class="filters__label">{{ row.label }}</span>
      <div class="filters__chips">
        <button
          type="button"
          class="chip"
          :class="{ 'chip--active': !state[row.key] }"
          :aria-pressed="!state[row.key]"
          @click="emit('filter', row.key)"
        >
          全部
        </button>
        <button
          v-for="item in row.options"
          :key="item.value"
          type="button"
          class="chip"
          :class="{ 'chip--active': state[row.key] === item.value }"
          :aria-pressed="state[row.key] === item.value"
          @click="emit('filter', row.key, String(item.value))"
        >
          {{ item.label }}
        </button>
        <button
          v-if="row.key === 'sector' && sectors.length > 8"
          type="button"
          class="filters__more"
          :aria-expanded="sectorsExpanded"
          @click="sectorsExpanded = !sectorsExpanded"
        >
          {{ sectorsExpanded ? '收起 −' : '更多板块 +' }}
        </button>
      </div>
    </div>
    <div class="filters__foot">
      <FilterDropdown
        :model-value="state.period"
        label="区间"
        :options="periods"
        @update:model-value="emit('period', $event)"
      />
      <FilterDropdown
        :model-value="state.sort_by"
        label="排序"
        :options="sorts"
        @update:model-value="emit('sort', $event as FundSortBy)"
      />
      <button type="button" class="chip" @click="emit('direction')">
        {{ state.sort_order === 'asc' ? '从低到高 ↑' : '从高到低 ↓' }}
      </button>
      <button type="button" class="filters__reset" @click="emit('reset')">重置全部</button>
    </div>
  </section>
</template>

<style scoped src="~/assets/css/fund-filters.css"></style>
