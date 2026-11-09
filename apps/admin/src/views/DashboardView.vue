<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fromNow, formatDateTime } from '@project/shared'

import { dashboardApi } from '@/api'
import EngagementPanel from '@/components/dashboard/EngagementPanel.vue'
import { useAuthStore } from '@/stores/auth'
import type { DashboardOverview } from '@/types/admin'

const router = useRouter()
const authStore = useAuthStore()

const overview = ref<DashboardOverview | null>(null)
const loading = ref(true)

const refreshTimer = ref<ReturnType<typeof setInterval>>()

onMounted(async () => {
  try {
    overview.value = await dashboardApi.overview()
  } finally {
    loading.value = false
  }
  // 每分钟刷新一次服务器时间，展示"活着"的后台
  refreshTimer.value = setInterval(async () => {
    overview.value = await dashboardApi.overview().catch(() => overview.value ?? null)
  }, 60_000)
})

onBeforeUnmount(() => {
  if (refreshTimer.value) clearInterval(refreshTimer.value)
})

/** 核心指标卡：点击跳到对应模块 */
const cards = computed(() => [
  {
    label: '基金总数',
    icon: 'Coin',
    to: 'funds',
    value: overview.value?.funds_total ?? 0,
    hint: overview.value
      ? `公司 ${overview.value.companies_total} · 经理 ${overview.value.managers_total}`
      : '',
  },
  {
    label: '用户总数',
    icon: 'User',
    to: 'users',
    value: overview.value?.user_total ?? 0,
    hint: overview.value ? `近 7 日新增 ${overview.value.user_new_7d}` : '',
  },
  {
    label: '文章总数',
    icon: 'Document',
    to: 'articles',
    value: overview.value?.article_total ?? 0,
    hint: overview.value ? `已发布 ${overview.value.article_published}` : '',
  },
  {
    label: '自选关注',
    icon: 'Star',
    to: 'funds',
    value: overview.value?.favorite_total ?? 0,
    hint: '用户添加的基金自选',
  },
])

/** 净值新鲜度：lag<=1 天视为健康 */
const navFreshness = computed(() => {
  const data = overview.value
  if (!data) return { text: '正在核对净值', type: 'info' as const }
  return {
    text: data.freshness_message || '暂无净值',
    type:
      data.freshness_state === 'current'
        ? ('success' as const)
        : data.freshness_state === 'lagging'
          ? ('warning' as const)
          : ('info' as const),
  }
})

/** 类型分布条宽：按最大计数归一化 */
const maxTypeCount = computed(() =>
  Math.max(1, ...(overview.value?.type_distribution.map((t) => t.count) ?? [1])),
)

function distWidth(count: number): string {
  return `${Math.max(4, Math.round((count / maxTypeCount.value) * 100))}%`
}

function actionLabel(method: string): string {
  if (method === 'POST') return '新增'
  if (method === 'PUT' || method === 'PATCH') return '修改'
  if (method === 'DELETE') return '删除'
  return method
}

/** 千分位：1,234,567 */
function fmtNum(value: number): string {
  return value.toLocaleString('zh-CN')
}
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">仪表盘</h2>
      <span class="muted">
        欢迎回来，{{ authStore.displayName }} · 服务器时间
        {{ overview ? formatDateTime(overview.server_time) : '—' }}
      </span>
    </div>

    <el-row :gutter="16" class="stat-row">
      <el-col v-for="card in cards" :key="card.label" :xs="12" :sm="6">
        <div class="card stat" @click="router.push({ name: card.to })">
          <div class="stat__icon">
            <el-icon :size="22"><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat__body">
            <div class="stat__label">{{ card.label }}</div>
            <div class="stat__value">
              <el-skeleton v-if="loading" :rows="0" animated style="width: 72px" />
              <template v-else>{{ fmtNum(card.value) }}</template>
            </div>
            <div class="stat__hint">{{ card.hint }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 左：数据覆盖率 -->
      <el-col :xs="24" :lg="10">
        <div class="card">
          <div class="card-head">
            <h3 class="section-title">数据覆盖率</h3>
            <el-tag v-if="overview" :type="navFreshness.type" size="small" effect="light">
              {{ navFreshness.text }}
            </el-tag>
          </div>
          <el-skeleton v-if="loading" :rows="6" animated />
          <template v-else>
            <p v-if="!overview?.coverage.length" class="empty">暂无覆盖率数据</p>
            <div v-for="item in overview?.coverage" :key="item.key" class="coverage">
              <div class="coverage__meta">
                <span>{{ item.label }}</span>
                <span class="muted">{{ item.covered }} / {{ item.total }}</span>
              </div>
              <el-progress
                :percentage="item.percent"
                :stroke-width="8"
                :color="item.percent >= 80 ? '#2563eb' : item.percent >= 40 ? '#f59e0b' : '#ef4444'"
              />
            </div>
            <div class="nav-latest muted">最新净值日期：{{ overview?.nav_latest_date ?? '—' }}</div>
          </template>
        </div>
      </el-col>

      <!-- 右：类型分布 + 最近用户 -->
      <el-col :xs="24" :lg="14">
        <div class="card">
          <div class="card-head">
            <h3 class="section-title">基金类型分布</h3>
            <router-link class="more" :to="{ name: 'funds' }">查看全部 →</router-link>
          </div>
          <el-skeleton v-if="loading" :rows="4" animated />
          <template v-else>
            <p v-if="!overview?.type_distribution.length" class="empty">暂无分布数据</p>
            <div
              v-for="item in overview?.type_distribution"
              :key="item.type"
              class="dist"
              @click="router.push({ name: 'funds' })"
            >
              <span class="dist__label">{{ item.label }}</span>
              <div class="dist__bar">
                <div class="dist__fill" :style="{ width: distWidth(item.count) }" />
              </div>
              <span class="dist__count muted">{{ fmtNum(item.count) }}</span>
            </div>
          </template>
        </div>

        <div class="card">
          <div class="card-head">
            <h3 class="section-title">最近注册会员</h3>
            <router-link class="more" :to="{ name: 'users' }">会员管理 →</router-link>
          </div>
          <el-skeleton v-if="loading" :rows="3" animated />
          <el-table v-else :data="overview?.recent_users ?? []" size="small" stripe>
            <el-table-column prop="username" label="用户名" min-width="120" />
            <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.email ?? '—' }}</template>
            </el-table-column>
            <el-table-column label="注册时间" width="130">
              <template #default="{ row }">{{ fromNow(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>

    <!-- 最近操作日志 -->
    <EngagementPanel />

    <div class="card">
      <div class="card-head">
        <h3 class="section-title">最近操作</h3>
        <router-link v-if="authStore.isSuperuser" class="more" :to="{ name: 'audit-logs' }">
          全部日志 →
        </router-link>
      </div>
      <el-skeleton v-if="loading" :rows="3" animated />
      <el-table v-else :data="overview?.recent_audits ?? []" size="small" stripe>
        <el-table-column prop="username" label="操作人" width="120">
          <template #default="{ row }">{{ row.username ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-tag
              :type="
                row.method === 'DELETE' ? 'danger' : row.method === 'POST' ? 'success' : 'warning'
              "
              size="small"
            >
              {{ actionLabel(row.method) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource" label="对象" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <span :class="row.status_code < 400 ? 'ok' : 'fail'">{{ row.status_code }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="130">
          <template #default="{ row }">{{ fromNow(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <p v-if="!loading && !overview?.recent_audits.length" class="empty">
        暂无操作记录——后台的写操作（增删改）都会自动记录在这里
      </p>
    </div>
  </div>
</template>

<style scoped lang="scss">
.muted {
  font-size: 13px;
  color: $text-secondary;
}

.stat-row {
  margin-bottom: 4px;
}

.stat {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 16px;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgb(16 24 40 / 8%);
  }

  &__icon {
    display: grid;
    flex: none;
    place-items: center;
    width: 44px;
    height: 44px;
    color: $color-primary;
    background: rgb(37 99 235 / 10%);
    border-radius: 10px;
  }

  &__label {
    font-size: 13px;
    color: $text-secondary;
  }

  &__value {
    margin-top: 2px;
    font-size: 24px;
    font-weight: 600;
    line-height: 1.2;
  }

  &__hint {
    margin-top: 2px;
    overflow: hidden;
    font-size: 12px;
    color: $text-secondary;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;

  .section-title {
    margin: 0;
  }
}

.section-title {
  margin: 0 0 16px;
  font-size: 15px;
  font-weight: 600;
}

.more {
  font-size: 13px;
  color: $color-primary;
  text-decoration: none;
}

.coverage {
  margin-bottom: 14px;

  &__meta {
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
    font-size: 13px;
  }
}

.nav-latest {
  padding-top: 4px;
  text-align: right;
}

.dist {
  display: grid;
  grid-template-columns: 72px 1fr 72px;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
  font-size: 13px;
  cursor: pointer;

  &__label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__bar {
    height: 10px;
    overflow: hidden;
    background: $bg-page;
    border-radius: 5px;
  }

  &__fill {
    height: 100%;
    background: $color-primary;
    border-radius: 5px;
    transition: width 0.4s ease;
  }

  &__count {
    text-align: right;
  }
}

.ok {
  color: #16a34a;
}

.fail {
  color: #ef4444;
}

.empty {
  margin: 8px 0;
  font-size: 13px;
  color: $text-secondary;
  text-align: center;
}
</style>
