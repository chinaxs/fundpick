<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { dashboardApi } from '@/api'
import type { EngagementSummary } from '@/types/admin'

/** 运营效果：活跃、回访、留存与转化。比例在这里算，后端只给原始计数。 */
const data = ref<EngagementSummary | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await dashboardApi.engagement()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载运营指标失败'
  } finally {
    loading.value = false
  }
}

function rate(part: number, total: number) {
  if (!total) return '—'
  return `${Math.round((part / total) * 100)}%`
}

const cards = computed(() => {
  if (!data.value) return []
  const d = data.value
  return [
    {
      key: 'active',
      label: '7 日活跃',
      value: d.active_7d.toLocaleString('zh-CN'),
      hint: `30 日 ${d.active_30d.toLocaleString('zh-CN')} · 占会员 ${rate(d.active_7d, d.total_users)}`,
    },
    {
      key: 'returning',
      label: '7 日回访',
      value: d.returning_7d.toLocaleString('zh-CN'),
      hint: '7 天内至少在 2 个不同日期登录',
    },
    {
      key: 'retention',
      label: '次周留存',
      value: rate(d.retention_7d, d.retention_cohort),
      hint: `7–14 天前注册 ${d.retention_cohort} 人，回来 ${d.retention_7d} 人`,
    },
    {
      key: 'favorite',
      label: '关注转化',
      value: rate(d.users_with_favorite, d.total_users),
      hint: `${d.users_with_favorite} 人有自选`,
    },
    {
      key: 'trade',
      label: '记账转化',
      value: rate(d.users_with_transaction, d.total_users),
      hint: `${d.users_with_transaction} 人有交易记录`,
    },
  ]
})

/** 按日活跃的柱高：以窗口内最大值归一化，空数据不出图 */
const bars = computed(() => {
  const points = data.value?.daily_active ?? []
  const max = Math.max(1, ...points.map((point) => point.users))
  return points.map((point) => ({
    day: point.day.slice(5),
    users: point.users,
    height: Math.round((point.users / max) * 100),
  }))
})

onMounted(() => void load())
</script>

<template>
  <div class="card">
    <div class="card-head">
      <div>
        <h3 class="section-title">运营效果</h3>
        <p v-if="data" class="hint">{{ data.excluded_note }}</p>
      </div>
      <el-button size="small" :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-alert v-if="error" type="error" :closable="false" :title="error" show-icon />
    <el-skeleton v-else-if="loading" :rows="3" animated />

    <template v-else-if="data">
      <el-row :gutter="12">
        <el-col v-for="item in cards" :key="item.key" :xs="12" :sm="8" :lg="4">
          <div class="metric">
            <div class="metric__label">{{ item.label }}</div>
            <div class="metric__value">{{ item.value }}</div>
            <div class="metric__hint">{{ item.hint }}</div>
          </div>
        </el-col>
      </el-row>

      <div v-if="bars.length" class="chart">
        <div class="chart__title">近 14 天日活（按日去重）</div>
        <div class="chart__bars">
          <div
            v-for="bar in bars"
            :key="bar.day"
            class="chart__col"
            :title="`${bar.day} · ${bar.users} 人`"
          >
            <div class="chart__bar" :style="{ height: `${Math.max(bar.height, 2)}%` }" />
            <span class="chart__day">{{ bar.day }}</span>
          </div>
        </div>
      </div>

      <p class="definitions">{{ data.definitions }}</p>
    </template>
  </div>
</template>

<style scoped lang="scss">
.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: $text-secondary;
}

.metric {
  padding: 12px;
  margin-bottom: 10px;
  background: $bg-page;
  border-radius: $radius-base;

  &__label {
    font-size: 12.5px;
    color: $text-secondary;
  }

  &__value {
    margin: 2px 0;
    font-size: 20px;
    font-weight: 600;
    line-height: 1.3;
  }

  &__hint {
    font-size: 11.5px;
    line-height: 1.5;
    color: $text-secondary;
  }
}

.chart {
  margin-top: 16px;

  &__title {
    margin-bottom: 8px;
    font-size: 12.5px;
    color: $text-secondary;
  }

  &__bars {
    display: flex;
    gap: 6px;
    align-items: flex-end;
    height: 96px;
    padding: 0 2px;
    border-bottom: 1px solid $border-color;
  }

  &__col {
    display: flex;
    flex: 1;
    flex-direction: column;
    justify-content: flex-end;
    align-items: center;
    height: 100%;
  }

  &__bar {
    width: 100%;
    min-height: 2px;
    background: rgb(37 99 235 / 65%);
    border-radius: 3px 3px 0 0;
  }

  &__day {
    margin-top: 4px;
    font-size: 10.5px;
    color: $text-secondary;
    white-space: nowrap;
  }
}

.definitions {
  margin: 14px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: $text-secondary;
}
</style>
