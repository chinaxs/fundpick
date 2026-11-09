<script setup lang="ts">
import type { FundQuery } from '@project/shared'
import {
  FUND_PERIOD_MAP,
  FUND_TYPE_MAP,
  FUND_SECTOR_MAP,
  RISK_LEVEL_MAP,
  FUND_SORT_MAP,
} from '@project/shared'
const { state, keyword, composing, update, applyKeyword, reset, sort, setPeriod, toggleFilter } =
  useFundScreener()
const { user } = useAuth()
const { load: loadFavorites } = useFavorites()
await loadFavorites()
watch(
  () => user.value?.id,
  () => loadFavorites(true),
)
const [{ data: filters }, { data, pending, error, refresh }] = await Promise.all([
  useFundFilters(),
  useFundList(state),
])
const totalPages = computed(() => Math.max(1, Math.ceil((data.value?.total ?? 0) / 20)))
const results = ref<HTMLElement | null>(null)
const activeFilters = computed(() =>
  [
    {
      key: 'keyword',
      label: state.value.keyword ? `搜索：${state.value.keyword}` : '',
      active: !!state.value.keyword,
    },
    {
      key: 'type',
      label: state.value.type ? FUND_TYPE_MAP[state.value.type] : '',
      active: !!state.value.type,
    },
    {
      key: 'sector',
      label: state.value.sector ? FUND_SECTOR_MAP[state.value.sector] : '',
      active: !!state.value.sector,
    },
    {
      key: 'risk_level',
      label: state.value.risk_level ? RISK_LEVEL_MAP[state.value.risk_level] : '',
      active: !!state.value.risk_level,
    },
    { key: 'company_id', label: '已限定基金公司', active: !!state.value.company_id },
  ].filter((item) => item.active),
)
function removeFilter(key: string) {
  if (key === 'keyword') keyword.value = ''
  return update({ [key]: undefined })
}
function preset(query: FundQuery) {
  keyword.value = ''
  return update({
    keyword: '',
    type: undefined,
    sector: undefined,
    risk_level: undefined,
    company_id: undefined,
    ...query,
  })
}
async function goPage(page: number) {
  await update({ page: Math.min(Math.max(1, page), totalPages.value) })
  results.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
useSeoMeta({
  title: '基金筛选',
  description: '按类型、主题、风险、收益、最大回撤与夏普筛选基金，加入关注后在工作台持续观察。',
})
</script>

<template>
  <div class="page">
    <div class="container">
      <header class="page__head">
        <div>
          <p class="section__eyebrow">FUND SCREENER</p>
          <h1 class="page__title">基金筛选</h1>
          <p class="page__desc">筛选基金，直接买入或添加关注。</p>
        </div>
        <NuxtLink to="/dashboard" class="btn btn--ghost">我的工作台 →</NuxtLink>
      </header>
      <FundsFilters
        v-model:keyword="keyword"
        :state="state"
        :filters="filters"
        @filter="toggleFilter"
        @period="setPeriod"
        @sort="sort"
        @search="applyKeyword"
        @composition="composing = $event"
        @reset="reset"
        @preset="preset"
        @direction="update({ sort_order: state.sort_order === 'asc' ? 'desc' : 'asc' })"
      />
      <div v-if="activeFilters.length" class="active-filters" aria-label="已选筛选条件">
        <button
          v-for="item in activeFilters"
          :key="item.key"
          type="button"
          :aria-label="`移除${item.label}`"
          @click="removeFilter(item.key)"
        >
          {{ item.label }} ×
        </button>
        <button type="button" class="clear" @click="reset">清空条件</button>
      </div>
      <div ref="results" class="results-head" aria-live="polite" style="scroll-margin-top: 90px">
        <strong>{{
          pending
            ? '正在筛选…'
            : error
              ? '结果暂不可用'
              : `找到 ${(data?.total ?? 0).toLocaleString()} 只基金`
        }}</strong>
        <small
          >{{ FUND_PERIOD_MAP[state.period] }} · {{ FUND_SORT_MAP[state.sort_by]
          }}{{ state.sort_order === 'asc' ? '从低到高' : '从高到低' }} · 星标加入关注</small
        >
      </div>
      <p class="screener-note">官方净值 T+1，日期见每只基金。买入为模拟记录。</p>
      <div v-if="pending" class="skeleton" role="status" aria-label="正在加载基金列表">
        <div v-for="i in 8" :key="i" class="skeleton__row" />
      </div>
      <div v-else-if="error" class="empty" role="alert">
        <h2 class="empty__title">基金列表加载失败</h2>
        <p class="empty__desc">请稍后重试，已选条件会保留。</p>
        <button type="button" class="btn" @click="refresh()">重新加载</button>
      </div>
      <div v-else-if="!data?.items.length" class="empty">
        <h2 class="empty__title">没有符合条件的基金</h2>
        <p class="empty__desc">可以移除上方某个条件，或重置后重新筛选。</p>
        <button type="button" class="btn" @click="reset">重置筛选</button>
      </div>
      <FundsResults
        v-else
        :items="data.items"
        :page="state.page"
        :period="state.period"
        :sort-by="state.sort_by"
        :sort-order="state.sort_order"
        @sort="sort"
      />
      <nav v-if="!error && totalPages > 1" class="pager" aria-label="基金列表分页">
        <button
          type="button"
          class="pager__btn"
          :disabled="state.page <= 1 || pending"
          @click="goPage(1)"
        >
          首页
        </button>
        <button
          type="button"
          class="pager__btn"
          :disabled="state.page <= 1 || pending"
          @click="goPage(state.page - 1)"
        >
          上一页
        </button>
        <span class="pager__info num" aria-current="page">{{ state.page }} / {{ totalPages }}</span>
        <button
          type="button"
          class="pager__btn"
          :disabled="state.page >= totalPages || pending"
          @click="goPage(state.page + 1)"
        >
          下一页
        </button>
        <button
          type="button"
          class="pager__btn"
          :disabled="state.page >= totalPages || pending"
          @click="goPage(totalPages)"
        >
          末页
        </button>
      </nav>
      <p class="disclaimer">
        风险等级与主题板块按规则推导。历史表现不代表未来收益，数据仅供研究参考，不构成投资建议。
      </p>
    </div>
  </div>
</template>

<style scoped src="~/assets/css/fund-screener.css"></style>
