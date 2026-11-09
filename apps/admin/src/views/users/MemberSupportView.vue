<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { formatDate } from '@project/shared'
import type { MemberPortfolioSummary, MemberSupportSummary } from '@project/shared'

import { supportApi } from '@/api'

/** 会员排查：只读概览 + 交易明细。查看明细会写审计。 */
const route = useRoute()
const router = useRouter()
const userId = computed(() => Number(route.params.id))

const member = ref<MemberSupportSummary | null>(null)
const portfolio = ref<MemberPortfolioSummary | null>(null)
const loading = ref(true)
const portfolioLoading = ref(false)

const kindLabel: Record<string, string> = { buy: '买入', sell: '卖出' }
const sourceLabel: Record<string, string> = {
  receipt: '平台回执',
  estimated: '系统估算',
  calculated: '系统计算',
  legacy: '旧估算',
}

async function loadMember() {
  loading.value = true
  try {
    member.value = await supportApi.member(userId.value)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载会员信息失败')
  } finally {
    loading.value = false
  }
}

async function loadPortfolio() {
  portfolioLoading.value = true
  try {
    portfolio.value = await supportApi.memberPortfolio(userId.value)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载交易明细失败')
  } finally {
    portfolioLoading.value = false
  }
}

function money(value: number | null) {
  if (value === null) return '—'
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

onMounted(() => {
  void loadMember()
  void loadPortfolio()
})
</script>

<template>
  <div class="page">
    <div class="page__header">
      <div>
        <h2 class="page__title">会员排查</h2>
        <p class="muted">只读视图。金额与份额以平台回执或会员本人确认为准，后台不提供修改入口。</p>
      </div>
      <el-button @click="router.back()">返回</el-button>
    </div>

    <div v-loading="loading" class="card">
      <template v-if="member">
        <div class="summary">
          <div class="summary__main">
            <h3>{{ member.full_name || member.username }}</h3>
            <p class="muted">
              @{{ member.username }} · {{ member.email || '未填写邮箱' }} ·
              {{ member.is_active ? '正常' : '已禁用' }}
            </p>
          </div>
          <div class="summary__stats">
            <div>
              <span>关注</span><strong>{{ member.favorite_count }}</strong>
            </div>
            <div>
              <span>交易</span><strong>{{ member.transaction_count }}</strong>
            </div>
            <div>
              <span>旧持仓</span><strong>{{ member.position_count }}</strong>
            </div>
            <div>
              <span>待处理反馈</span><strong>{{ member.open_feedback }}</strong>
            </div>
            <div>
              <span>待核实重置</span><strong>{{ member.pending_reset }}</strong>
            </div>
          </div>
        </div>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="注册时间">
            {{ formatDate(member.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="最近登录">
            {{ formatDate(member.last_login_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="会员 ID">{{ member.id }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </div>

    <div class="card">
      <div class="card-head">
        <h3 class="section-title">交易明细</h3>
        <el-button size="small" :loading="portfolioLoading" @click="loadPortfolio">刷新</el-button>
      </div>

      <el-alert
        v-if="portfolio"
        type="info"
        :closable="false"
        show-icon
        :title="portfolio.note"
        class="note"
      />

      <el-table
        v-loading="portfolioLoading"
        :data="portfolio?.items ?? []"
        size="small"
        border
        empty-text="该会员还没有已确认的交易"
      >
        <el-table-column prop="fund_code" label="代码" width="100" />
        <el-table-column prop="fund_name" label="基金" min-width="160" show-overflow-tooltip />
        <el-table-column label="方向" width="80">
          <template #default="{ row }">{{ kindLabel[row.kind] ?? row.kind }}</template>
        </el-table-column>
        <el-table-column label="确认日" width="115">
          <template #default="{ row }">{{ formatDate(row.confirmed_on) }}</template>
        </el-table-column>
        <el-table-column label="金额" width="120" align="right">
          <template #default="{ row }">{{ money(row.amount) }}</template>
        </el-table-column>
        <el-table-column label="份额" width="120" align="right">
          <template #default="{ row }">{{ money(row.shares) }}</template>
        </el-table-column>
        <el-table-column label="净值" width="100" align="right">
          <template #default="{ row }">{{ money(row.nav) }}</template>
        </el-table-column>
        <el-table-column label="费用" width="100" align="right">
          <template #default="{ row }">{{ money(row.fee) }}</template>
        </el-table-column>
        <el-table-column label="来源" width="110">
          <template #default="{ row }">{{
            sourceLabel[row.record_source] ?? row.record_source
          }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.voided_at" type="info" size="small" effect="light">已作废</el-tag>
            <el-tag v-else type="success" size="small" effect="light">已确认</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <p v-if="portfolio?.truncated" class="muted">
        仅展示最近 {{ portfolio.items.length }} 条（共 {{ portfolio.total }} 条）。
      </p>
    </div>

    <div v-if="portfolio?.positions.length" class="card">
      <div class="card-head">
        <h3 class="section-title">旧持仓记录</h3>
      </div>
      <el-table :data="portfolio.positions" size="small" border>
        <el-table-column prop="fund_code" label="代码" width="100" />
        <el-table-column prop="fund_name" label="基金" min-width="180" show-overflow-tooltip />
        <el-table-column label="份额" width="130" align="right">
          <template #default="{ row }">{{ money(row.shares) }}</template>
        </el-table-column>
        <el-table-column label="成本" width="130" align="right">
          <template #default="{ row }">{{ money(row.cost) }}</template>
        </el-table-column>
        <el-table-column label="市值" width="130" align="right">
          <template #default="{ row }">{{ money(row.market_value) }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped lang="scss">
.muted {
  font-size: 12.5px;
  color: $text-secondary;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;

  h3 {
    margin: 0 0 4px;
    font-size: 18px;
  }

  &__stats {
    display: flex;
    flex-wrap: wrap;
    gap: 24px;

    div {
      display: flex;
      flex-direction: column;
      font-size: 12.5px;
      color: $text-secondary;
    }

    strong {
      font-size: 18px;
      color: $text-primary;
    }
  }
}

.note {
  margin-bottom: 12px;
}
</style>
