<script setup lang="ts">
/**
 * 用一次性链接设置新密码。
 *
 * 令牌在 URL query 里，页面本身不登录也能访问；重置成功后该账号
 * 所有旧会话失效，需要重新登录。
 */
const route = useRoute()
const apiBase = useApiBase()
const token = computed(() => String(route.query.token ?? ''))

const password = ref('')
const confirm = ref('')
const submitting = ref(false)
const done = ref(false)
const error = ref('')

async function submit() {
  if (submitting.value) return
  if (!token.value) {
    error.value = '链接不完整，请让客服重新生成。'
    return
  }
  if (password.value.length < 8) {
    error.value = '密码至少 8 位。'
    return
  }
  if (password.value !== confirm.value) {
    error.value = '两次输入的密码不一致。'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    await $fetch('/portal/auth/reset-password', {
      baseURL: apiBase,
      method: 'POST',
      body: { token: token.value, new_password: password.value },
    })
    done.value = true
  } catch (err) {
    const data = (err as { data?: { message?: string } } | null)?.data
    error.value = data?.message || '重置失败，链接可能已过期。'
  } finally {
    submitting.value = false
  }
}

useSeoMeta({
  title: '设置新密码',
  description: '使用一次性链接重设登录密码。',
  robots: 'noindex, nofollow',
})
</script>

<template>
  <div class="page">
    <div class="container">
      <div class="card">
        <h1>设置新密码</h1>

        <template v-if="done">
          <div class="done" role="status">
            密码已重置，原设备上的登录已全部失效，请用新密码重新登录。
          </div>
          <NuxtLink to="/" class="btn">去登录</NuxtLink>
        </template>

        <template v-else>
          <p class="lead">链接 30 分钟内有效，且只能使用一次。</p>
          <label class="field">
            <span class="field__label">新密码</span>
            <input
              v-model="password"
              type="password"
              class="field__control"
              autocomplete="new-password"
              placeholder="至少 8 位"
            />
          </label>
          <label class="field">
            <span class="field__label">确认新密码</span>
            <input
              v-model="confirm"
              type="password"
              class="field__control"
              autocomplete="new-password"
              @keyup.enter="submit"
            />
          </label>
          <button type="button" class="btn" :disabled="submitting" @click="submit">
            {{ submitting ? '提交中…' : '确认重置' }}
          </button>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
        </template>

        <p class="footer">
          <NuxtLink to="/forgot-password">重新申请链接</NuxtLink>
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
  max-width: 480px;
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
  margin: 0 0 20px;
  font-size: 14px;
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
  display: block;
  width: 100%;
  padding: 10px;
  font-size: 15px;
  color: #fff;
  text-align: center;
  text-decoration: none;
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
  margin-bottom: 18px;
  font-size: 14px;
  line-height: 1.7;
  color: #047857;
  background: #ecfdf5;
  border-radius: var(--radius-sm);
}

.error {
  margin-top: 12px;
  font-size: 13px;
  color: var(--up);
}

.footer {
  margin: 20px 0 0;
  font-size: 13px;
}

.footer a {
  color: var(--brand);
  text-decoration: none;
}
</style>
