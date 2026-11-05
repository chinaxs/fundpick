<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  DEFAULT_PAGE_SIZE,
  FUND_TYPE_MAP,
  PAGE_SIZE_OPTIONS,
  type FundListItem,
  type FundType,
} from '@project/shared'

import { fundApi } from '@/api'

const loading = ref(false)
const rows = ref<FundListItem[]>([])
const total = ref(0)
const syncStatus = ref<{
  fund_total: number
  nav_rows: number
  latest_nav_date: string | null
} | null>(null)

const query = reactive({
  page: 1,
  page_size: DEFAULT_PAGE_SIZE,
  keyword: '',
  type: undefined as FundType | undefined,
  period: '1y',
  sort_by: 'return',
  sort_order: 'desc',
})

const typeOptions = Object.entries(FUND_TYPE_MAP).map(([value, label]) => ({
  value: value as FundType,
  label,
}))

async function fetchList() {
  loading.value = true
  try {
    const result = await fundApi.list({
      page: query.page,
      page_size: query.page_size,
      keyword: query.keyword || undefined,
      type: query.type,
      period: query.period as never,
      sort_by: 'return',
      sort_order: 'desc',
    })
    rows.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function fetchStatus() {
  syncStatus.value = await fundApi.syncStatus()
}

function handleSearch() {
  query.page = 1
  fetchList()
}

function resetQuery() {
  query.keyword = ''
  query.type = undefined
  query.page = 1
  fetchList()
}

function typeLabel(type: string): string {
  return FUND_TYPE_MAP[type as FundType] ?? type
}

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

onMounted(() => {
  fetchList()
  fetchStatus()
})
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">基金管理</h2>
      <el-tag type="info" effect="plain">数据源：AkShare（仅供开发验证）</el-tag>
    </div>

    <!-- 同步状态 -->
    <el-row :gutter="16">
      <el-col :xs="24" :sm="8">
        <div class="card stat">
          <div class="stat__label">基金总数</div>
          <div class="stat__value">{{ syncStatus?.fund_total?.toLocaleString() ?? '—' }}</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="8">
        <div class="card stat">
          <div class="stat__label">净值记录</div>
          <div class="stat__value">{{ syncStatus?.nav_rows?.toLocaleString() ?? '—' }}</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="8">
        <div class="card stat">
          <div class="stat__label">最新净值日期</div>
          <div class="stat__value">{{ syncStatus?.latest_nav_date ?? '—' }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="card">
      <div class="filter-bar">
        <el-input
          v-model="query.keyword"
          placeholder="基金代码 / 名称"
          clearable
          style="width: 220px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-select
          v-model="query.type"
          placeholder="基金类型"
          clearable
          style="width: 150px"
          @change="handleSearch"
        >
          <el-option
            v-for="item in typeOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-select v-model="query.period" style="width: 130px" @change="handleSearch">
          <el-option label="近1年" value="1y" />
          <el-option label="近3年" value="3y" />
          <el-option label="今年来" value="ytd" />
        </el-select>
        <el-button type="primary" plain @click="handleSearch">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="rows" stripe border>
        <el-table-column prop="code" label="代码" width="100" />
        <el-table-column prop="name" label="基金名称" min-width="220" show-overflow-tooltip />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ typeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="单位净值" width="110" align="right">
          <template #default="{ row }">{{ row.latest_nav?.toFixed(4) ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="区间收益" width="110" align="right">
          <template #default="{ row }">
            <span :class="(row.return_rate ?? 0) >= 0 ? 'up' : 'down'">
              {{ fmtPct(row.return_rate) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最大回撤" width="110" align="right">
          <template #default="{ row }">{{ fmtPct(row.max_drawdown) }}</template>
        </el-table-column>
        <el-table-column label="公司" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.company_name ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="经理" width="110">
          <template #default="{ row }">{{ row.manager_name ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="净值日期" width="130">
          <template #default="{ row }">{{ row.latest_nav_date ?? '—' }}</template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[...PAGE_SIZE_OPTIONS]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="fetchList"
        />
      </div>
    </div>

    <el-alert type="warning" :closable="false" show-icon>
      <template #title>数据采集说明</template>
      当前数据来自 AkShare（公开渠道），仅用于开发验证，不适用于商业产品。 全量基金基础数据可在 1
      分钟内同步完成；风险指标（回撤/夏普/波动）需逐只请求，建议后台分批跑：
      <code>python -m scripts.sync_funds --mode risk --limit 600</code>
    </el-alert>
  </div>
</template>

<style scoped lang="scss">
.stat {
  margin-bottom: 16px;

  &__label {
    font-size: 13px;
    color: $text-secondary;
  }

  &__value {
    margin-top: 6px;
    font-size: 24px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
}

.up {
  color: $color-danger;
  font-weight: 600;
}

.down {
  color: $color-success;
  font-weight: 600;
}

code {
  padding: 1px 4px;
  font-size: 12px;
  background: rgb(0 0 0 / 6%);
  border-radius: 4px;
}
</style>
