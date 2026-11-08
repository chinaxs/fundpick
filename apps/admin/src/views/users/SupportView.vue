<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { FEEDBACK_CATEGORY_MAP, FEEDBACK_STATUS_MAP, formatDate } from '@project/shared'
import type { FeedbackStatus, PasswordResetRequestItem } from '@project/shared'

import { supportApi } from '@/api'
import type { FeedbackQuery, FeedbackRow } from '@/types/admin'

/** 会员支持：反馈工单处理 + 密码重置申请。 */
const tab = ref<'feedback' | 'reset'>('feedback')

// ---- 反馈 ----
const rows = ref<FeedbackRow[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive<FeedbackQuery>({
  page: 1,
  page_size: 20,
  status: '',
  category: '',
  keyword: '',
})
const drawerVisible = ref(false)
const current = ref<FeedbackRow | null>(null)
const replyForm = reactive<{ status: FeedbackStatus; reply: string }>({
  status: 'processing',
  reply: '',
})
const saving = ref(false)

const statusOptions = Object.entries(FEEDBACK_STATUS_MAP).map(([value, item]) => ({
  value,
  label: item.label,
}))
const categoryOptions = Object.entries(FEEDBACK_CATEGORY_MAP).map(([value, label]) => ({
  value,
  label,
}))

const pendingCount = computed(() => rows.value.filter((row) => row.status === 'open').length)

async function fetchFeedback() {
  loading.value = true
  try {
    const data = await supportApi.feedback({
      page: query.page,
      page_size: query.page_size,
      ...(query.status ? { status: query.status } : {}),
      ...(query.category ? { category: query.category } : {}),
      ...(query.keyword?.trim() ? { keyword: query.keyword.trim() } : {}),
    })
    rows.value = data.items
    total.value = data.total
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载反馈失败')
  } finally {
    loading.value = false
  }
}

function search() {
  query.page = 1
  void fetchFeedback()
}

function openFeedback(row: FeedbackRow) {
  current.value = row
  replyForm.status = row.status
  replyForm.reply = row.reply ?? ''
  drawerVisible.value = true
}

async function saveFeedback() {
  if (!current.value) return
  saving.value = true
  try {
    await supportApi.updateFeedback(current.value.id, {
      status: replyForm.status,
      reply: replyForm.reply.trim() || null,
    })
    ElMessage.success('已保存，会员可在反馈页看到回复')
    drawerVisible.value = false
    await fetchFeedback()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}

// ---- 密码重置 ----
const resets = ref<PasswordResetRequestItem[]>([])
const resetLoading = ref(false)
const resetStatus = ref<'pending' | 'issued' | 'used' | ''>('pending')
const linkVisible = ref(false)
const resetLink = ref<{ username: string; path: string; expires_at: string } | null>(null)

async function fetchResets() {
  resetLoading.value = true
  try {
    resets.value = await supportApi.passwordResets({
      ...(resetStatus.value ? { status: resetStatus.value } : {}),
      limit: 50,
    })
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载重置申请失败')
  } finally {
    resetLoading.value = false
  }
}

async function createLink(row: PasswordResetRequestItem) {
  try {
    const link = await supportApi.createResetLink(row.user_id)
    resetLink.value = {
      username: link.username,
      path: link.path,
      expires_at: link.expires_at,
    }
    linkVisible.value = true
    await fetchResets()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '生成链接失败')
  }
}

async function copyLink() {
  const value = resetLink.value?.path
  if (!value) return
  const absolute = `${window.location.origin.replace(/:\d+$/, ':3000')}${value}`
  try {
    await navigator.clipboard.writeText(absolute)
    ElMessage.success('链接已复制，请立即发给会员本人')
  } catch {
    ElMessage.warning('复制失败，请手动选择文本复制')
  }
}

function statusTag(status: string) {
  return FEEDBACK_STATUS_MAP[status]?.label ?? status
}

function statusType(status: string) {
  if (status === 'open') return 'warning'
  if (status === 'processing') return 'primary'
  if (status === 'resolved') return 'success'
  return 'info'
}

onMounted(() => {
  void fetchFeedback()
  void fetchResets()
})
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">会员支持</h2>
      <span class="muted">反馈 {{ total }} 条，待处理 {{ pendingCount }} 条</span>
    </div>

    <el-tabs v-model="tab">
      <el-tab-pane label="反馈工单" name="feedback">
        <div class="card">
          <div class="toolbar">
            <el-select
              v-model="query.status"
              clearable
              placeholder="状态"
              style="width: 130px"
              @change="search"
            >
              <el-option
                v-for="item in statusOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-select
              v-model="query.category"
              clearable
              placeholder="分类"
              style="width: 130px"
              @change="search"
            >
              <el-option
                v-for="item in categoryOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-input
              v-model="query.keyword"
              clearable
              placeholder="标题或内容关键词"
              style="width: 240px"
              @keyup.enter="search"
            />
            <el-button type="primary" :loading="loading" @click="search">查询</el-button>
          </div>

          <el-table v-loading="loading" :data="rows" border size="small" empty-text="暂无反馈">
            <el-table-column prop="id" label="#" width="70" />
            <el-table-column label="会员" width="150">
              <template #default="{ row }">{{ row.username || '—' }}</template>
            </el-table-column>
            <el-table-column label="分类" width="100">
              <template #default="{ row }">{{ FEEDBACK_CATEGORY_MAP[row.category] }}</template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" effect="light" size="small">
                  {{ statusTag(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="提交时间" width="170">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button
                  link
                  type="primary"
                  size="small"
                  @click="openFeedback(row as FeedbackRow)"
                >
                  处理
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-if="total > (query.page_size ?? 20)"
            v-model:current-page="query.page"
            :page-size="query.page_size"
            :total="total"
            layout="total, prev, pager, next"
            class="pagination"
            @current-change="fetchFeedback"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="密码重置" name="reset">
        <div class="card">
          <div class="toolbar">
            <el-radio-group v-model="resetStatus" @change="fetchResets">
              <el-radio-button value="pending">待核实</el-radio-button>
              <el-radio-button value="issued">已生成链接</el-radio-button>
              <el-radio-button value="used">已使用</el-radio-button>
              <el-radio-button value="">全部</el-radio-button>
            </el-radio-group>
            <span class="muted">
              核实身份后生成一次性链接，30 分钟内有效；生成后请当场发给本人。
            </span>
          </div>

          <el-table
            v-loading="resetLoading"
            :data="resets"
            border
            size="small"
            empty-text="暂无重置申请"
          >
            <el-table-column prop="id" label="#" width="70" />
            <el-table-column label="会员" width="150">
              <template #default="{ row }">{{ row.username || '—' }}</template>
            </el-table-column>
            <el-table-column label="邮箱" min-width="200">
              <template #default="{ row }">{{ row.email || '未填写' }}</template>
            </el-table-column>
            <el-table-column label="申请时间" width="170">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="来源 IP" width="140">
              <template #default="{ row }">{{ row.requested_ip || '—' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.used_at" type="info" effect="light" size="small">已使用</el-tag>
                <el-tag v-else-if="row.expires_at" type="success" effect="light" size="small">
                  已生成链接
                </el-tag>
                <el-tag v-else type="warning" effect="light" size="small">待核实</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="!row.used_at"
                  link
                  type="primary"
                  size="small"
                  @click="createLink(row as PasswordResetRequestItem)"
                >
                  生成链接
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-drawer v-model="drawerVisible" title="处理反馈" size="480px">
      <div v-if="current" class="detail">
        <div class="detail__meta">
          <span>#{{ current.id }} · {{ current.username || '未知会员' }}</span>
          <span>{{ formatDate(current.created_at) }}</span>
        </div>
        <p v-if="current.page_url" class="detail__page">页面：{{ current.page_url }}</p>
        <h4 class="detail__title">{{ current.title }}</h4>
        <p class="detail__content">{{ current.content }}</p>
        <p v-if="current.contact" class="detail__contact">联系方式：{{ current.contact }}</p>

        <el-divider />

        <el-form label-position="top">
          <el-form-item label="处理状态">
            <el-select v-model="replyForm.status" style="width: 100%">
              <el-option
                v-for="item in statusOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="回复会员（会显示在门户反馈页）">
            <el-input
              v-model="replyForm.reply"
              type="textarea"
              :rows="5"
              maxlength="2000"
              show-word-limit
              placeholder="说明原因、处理结果或需要会员补充的信息"
            />
          </el-form-item>
        </el-form>
        <div class="detail__actions">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveFeedback">保存</el-button>
        </div>
      </div>
    </el-drawer>

    <el-dialog v-model="linkVisible" title="一次性重置链接" width="620px">
      <template v-if="resetLink">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="令牌只显示这一次，关闭后无法再次查看"
          description="请核实身份后，把链接直接发给会员本人；有效期 30 分钟，使用后该账号所有会话失效。"
        />
        <p class="link-owner">会员：{{ resetLink.username }}</p>
        <el-input :model-value="resetLink.path" readonly />
        <p class="muted">过期时间：{{ formatDate(resetLink.expires_at) }}</p>
        <div class="detail__actions">
          <el-button type="primary" @click="copyLink">复制链接</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.muted {
  font-size: 12.5px;
  color: $text-secondary;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 14px;
}

.pagination {
  justify-content: flex-end;
  margin-top: 14px;
}

.detail {
  &__meta {
    display: flex;
    justify-content: space-between;
    font-size: 12.5px;
    color: $text-secondary;
  }

  &__page {
    margin: 10px 0 0;
    font-size: 12.5px;
    color: $text-secondary;
  }

  &__title {
    margin: 14px 0 8px;
    font-size: 16px;
  }

  &__content {
    font-size: 14px;
    line-height: 1.8;
    white-space: pre-wrap;
  }

  &__contact {
    font-size: 13px;
    color: $text-secondary;
  }

  &__actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
    margin-top: 16px;
  }
}

.link-owner {
  margin: 16px 0 8px;
  font-size: 13px;
  color: $text-regular;
}
</style>
