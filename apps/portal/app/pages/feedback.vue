<script setup lang="ts">
import type {
  ApiResponse,
  FeedbackCategory,
  FeedbackCreatePayload,
  FeedbackItem,
} from '@project/shared'
import { FEEDBACK_CATEGORY_MAP, FEEDBACK_STATUS_MAP } from '@project/shared'

/** 反馈：会员提交问题，并在同一页看到处理结果。 */
const { isLoggedIn, openAuth, ensureSession, authHeaders } = useAuth()
const apiBase = useApiBase()

await ensureSession()

const items = ref<FeedbackItem[]>([])
const loading = ref(false)
const submitting = ref(false)
const message = ref('')
const form = reactive<FeedbackCreatePayload>({
  category: 'other',
  title: '',
  content: '',
  contact: '',
  page_url: '',
})

const categories = Object.entries(FEEDBACK_CATEGORY_MAP).map(([value, label]) => ({
  value: value as FeedbackCategory,
  label,
}))

async function load() {
  if (!isLoggedIn.value) return
  loading.value = true
  try {
    const res = await $fetch<ApiResponse<FeedbackItem[]>>('/portal/feedback', {
      baseURL: apiBase,
      headers: authHeaders.value,
    })
    items.value = res.data ?? []
  } catch {
    message.value = '反馈列表加载失败，请刷新重试。'
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (submitting.value) return
  if (form.title.trim().length < 3 || form.content.trim().length < 10) {
    message.value = '标题至少 3 字，描述至少 10 字，方便我们定位问题。'
    return
  }
  submitting.value = true
  message.value = ''
  try {
    await $fetch('/portal/feedback', {
      baseURL: apiBase,
      method: 'POST',
      headers: authHeaders.value,
      body: {
        ...form,
        contact: form.contact?.trim() || null,
        page_url: form.page_url?.trim() || null,
      },
    })
    form.title = ''
    form.content = ''
    form.page_url = ''
    message.value = '已提交，处理结果会显示在下方。'
    await load()
  } catch (err) {
    const data = (err as { data?: { message?: string } } | null)?.data
    message.value = data?.message || '提交失败，请稍后重试。'
  } finally {
    submitting.value = false
  }
}

function statusLabel(status: string) {
  return FEEDBACK_STATUS_MAP[status]?.label ?? status
}

function statusTone(status: string) {
  return FEEDBACK_STATUS_MAP[status]?.tone ?? 'muted'
}

onMounted(() => void load())

useSeoMeta({
  title: '反馈与帮助',
  description: '提交使用问题或建议，查看处理进度。',
  robots: 'noindex, nofollow',
})
</script>

<template>
  <div class="feedback">
    <div class="container">
      <header class="head">
        <div>
          <h1>反馈与帮助</h1>
          <p class="head__sub">数据、账号、功能问题都可以在这里提交，处理结果会回到本页。</p>
        </div>
        <NuxtLink to="/about" class="text-link">使用说明</NuxtLink>
      </header>
      <MemberNav />

      <section v-if="!isLoggedIn" class="empty">
        <h2>登录后提交反馈</h2>
        <p>我们需要知道是哪个账号遇到问题，才能查到对应的记录。</p>
        <button type="button" class="btn" @click="openAuth('login')">登录 / 注册</button>
      </section>

      <template v-else>
        <form class="card form" @submit.prevent="submit">
          <label class="field">
            <span class="field__label">问题类型</span>
            <select v-model="form.category" class="field__control">
              <option v-for="item in categories" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
          </label>
          <label class="field">
            <span class="field__label">标题</span>
            <input
              v-model="form.title"
              class="field__control"
              maxlength="120"
              placeholder="一句话说明问题，如「净值日期不对」"
            />
          </label>
          <label class="field">
            <span class="field__label">详细描述</span>
            <textarea
              v-model="form.content"
              class="field__control field__control--area"
              rows="5"
              maxlength="2000"
              placeholder="出问题的页面、基金代码、你期望的结果。不要填写身份证、银行卡等敏感信息。"
            />
          </label>
          <div class="field-row">
            <label class="field">
              <span class="field__label">联系方式（可选）</span>
              <input
                v-model="form.contact"
                class="field__control"
                maxlength="120"
                placeholder="留空则用账号邮箱"
              />
            </label>
            <label class="field">
              <span class="field__label">页面地址（可选）</span>
              <input
                v-model="form.page_url"
                class="field__control"
                maxlength="255"
                placeholder="/funds/002910"
              />
            </label>
          </div>
          <div class="actions">
            <button type="submit" class="btn" :disabled="submitting">
              {{ submitting ? '提交中…' : '提交反馈' }}
            </button>
            <span v-if="message" class="hint">{{ message }}</span>
          </div>
        </form>

        <section class="list">
          <h2 class="list__title">我的反馈</h2>
          <p v-if="loading" class="hint">正在加载…</p>
          <p v-else-if="!items.length" class="hint">还没有提交过反馈。</p>
          <article v-for="item in items" :key="item.id" class="card item">
            <header class="item__head">
              <div>
                <span class="item__cat">{{ FEEDBACK_CATEGORY_MAP[item.category] }}</span>
                <strong>{{ item.title }}</strong>
              </div>
              <span class="tag" :class="`tag--${statusTone(item.status)}`">
                {{ statusLabel(item.status) }}
              </span>
            </header>
            <p class="item__content">{{ item.content }}</p>
            <p v-if="item.reply" class="item__reply">
              <span class="item__reply-label">回复</span>{{ item.reply }}
            </p>
            <footer class="item__meta">
              <span>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</span>
              <span v-if="item.handled_at">
                处理于 {{ new Date(item.handled_at).toLocaleString('zh-CN') }}
              </span>
            </footer>
          </article>
        </section>
      </template>
    </div>
  </div>
</template>

<style scoped>
.feedback {
  padding: 32px 0 64px;
}

.head {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 18px;
}

.head h1 {
  margin: 0 0 4px;
  font-size: 26px;
}

.head__sub {
  margin: 0;
  font-size: 14px;
  color: var(--muted);
}

.text-link {
  font-size: 14px;
  color: var(--brand);
  text-decoration: none;
}

.empty {
  padding: 56px 24px;
  text-align: center;
  background: var(--bg-soft);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

.empty h2 {
  margin: 0 0 8px;
  font-size: 18px;
}

.empty p {
  margin: 0 0 18px;
  color: var(--muted);
}

.btn {
  padding: 9px 20px;
  font-size: 14px;
  color: #fff;
  cursor: pointer;
  background: var(--brand);
  border: none;
  border-radius: 999px;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.card {
  padding: 20px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-xs);
}

.form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 28px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field__label {
  font-size: 13px;
  color: var(--ink-2);
}

.field__control {
  padding: 9px 12px;
  font-family: inherit;
  font-size: 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
}

.field__control--area {
  resize: vertical;
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.hint {
  font-size: 13px;
  color: var(--muted);
}

.list__title {
  margin: 0 0 12px;
  font-size: 17px;
}

.item {
  margin-bottom: 12px;
}

.item__head {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}

.item__cat {
  padding: 2px 8px;
  margin-right: 8px;
  font-size: 12px;
  color: var(--muted);
  background: var(--bg-soft);
  border-radius: 6px;
}

.item__content {
  margin: 10px 0;
  font-size: 14px;
  color: var(--ink-2);
  white-space: pre-wrap;
}

.item__reply {
  padding: 10px 12px;
  margin: 0 0 10px;
  font-size: 14px;
  background: var(--brand-soft);
  border-radius: var(--radius-sm);
}

.item__reply-label {
  margin-right: 8px;
  font-weight: 600;
  color: var(--brand);
}

.item__meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--muted-2);
}

.tag {
  padding: 2px 10px;
  font-size: 12px;
  border-radius: 999px;
}

.tag--warn {
  color: #b45309;
  background: #fffbeb;
}

.tag--info {
  color: #1d4ed8;
  background: var(--brand-soft);
}

.tag--ok {
  color: #047857;
  background: #ecfdf5;
}

.tag--muted {
  color: var(--muted);
  background: var(--bg-soft);
}

@media (max-width: 640px) {
  .field-row {
    grid-template-columns: 1fr;
  }
}
</style>
