<script setup lang="ts">
import type { ApiResponse } from '@project/shared'

/**
 * 申请重置密码。
 *
 * 这里刻意不承诺"已发送邮件"：后端没有邮件服务，客服核实身份后会线下
 * 发送一次性链接，所以文案要说清楚下一步会发生什么。
 */
const apiBase = useApiBase()

const account = ref('')
const submitting = ref(false)
const done = ref(false)
const error = ref('')
const serverMessage = ref('')

async function submit() {
  if (submitting.value) return
  if (account.value.trim().length < 3) {
    error.value = '请输入注册邮箱或登录名。'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    const res = await $fetch<ApiResponse<{ message: string }>>('/portal/auth/forgot-password', {
      baseURL: apiBase,
      method: 'POST',
      body: { account: account.value.trim() },
    })
    serverMessage.value = res.data?.message ?? ''
    done.value = true
  } catch (err) {
    const data = (err as { data?: { message?: string } } | null)?.data
    error.value = data?.message || '提交失败，请稍后重试。'
  } finally {
    submitting.value = false
  }
}

useSeoMeta({
  title: '找回密码',
  description: '提交密码重置申请，客服核实后发送一次性链接。',
  robots: 'noindex, nofollow',
})
</script>

<template>
  <div class="page">
    <div class="container">
      <div class="card">
        <h1>找回密码</h1>
        <p class="lead">
          提交注册邮箱或登录名。出于安全考虑，我们不会直接发送新密码：
          客服核实身份后，会通过你留存的联系方式发送一个 30 分钟内有效的一次性链接。
        </p>

        <template v-if="!done">
          <label class="field">
            <span class="field__label">注册邮箱 / 登录名</span>
            <input
              v-model="account"
              class="field__control"
              autocomplete="username"
              placeholder="例如 you@example.com"
              @keyup.enter="submit"
            />
          </label>
          <button type="button" class="btn" :disabled="submitting" @click="submit">
            {{ submitting ? '提交中…' : '提交申请' }}
          </button>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
        </template>

        <template v-else>
          <div class="done" role="status">
            {{ serverMessage || '已收到申请，请留意我们的回复。' }}
          </div>
          <p class="muted">
            如果注册邮箱已停用，可以在<NuxtLink to="/feedback">反馈页</NuxtLink>说明情况，
            客服会用其他方式核实身份。
          </p>
        </template>

        <p class="footer">
          <NuxtLink to="/">返回首页</NuxtLink>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 48px 0 72px;
}

.card {
  max-width: 520px;
  padding: 28px;
  margin: 0 auto;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
}

h1 {
  margin: 0 0 10px;
  font-size: 24px;
}

.lead {
  margin: 0 0 22px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--muted);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}

.field__label {
  font-size: 13px;
  color: var(--ink-2);
}

.field__control {
  padding: 10px 12px;
  font-family: inherit;
  font-size: 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
}

.btn {
  width: 100%;
  padding: 10px;
  font-size: 15px;
  color: #fff;
  cursor: pointer;
  background: var(--brand);
  border: none;
  border-radius: var(--radius-sm);
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.done {
  padding: 14px 16px;
  margin-bottom: 14px;
  font-size: 14px;
  color: #047857;
  background: #ecfdf5;
  border-radius: var(--radius-sm);
}

.error {
  margin-top: 12px;
  font-size: 13px;
  color: var(--up);
}

.muted {
  font-size: 13px;
  line-height: 1.8;
  color: var(--muted);
}

.footer {
  margin: 22px 0 0;
  font-size: 13px;
}

.footer a {
  color: var(--brand);
  text-decoration: none;
}
</style>
