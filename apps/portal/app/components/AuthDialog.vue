<script setup lang="ts">
/**
 * 全局登录 / 注册弹窗。
 *
 * 由 `useAuth().openAuth()` 唤起，挂载在 default 布局上，所有页面共享同一个实例。
 * 只在打开时渲染表单，关闭即销毁，不拖累首屏。
 */
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

const auth = useAuth()
const { dialogVisible, dialogMode } = auth

const loginFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()
const submitting = ref(false)

const loginForm = reactive({ username: '', password: '' })
const registerForm = reactive({ username: '', email: '', password: '', confirm: '' })

const loginRules: FormRules = {
  username: [{ required: true, message: '请输入用户名或邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const registerRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '长度需在 3–50 位之间', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_]+$/, message: '仅支持字母、数字与下划线', trigger: 'blur' },
  ],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, max: 72, message: '密码至少 8 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        if (value !== registerForm.password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

/** 后端统一响应体里的 message 优先展示，比通用文案更有用 */
function errorMessage(err: unknown, fallback: string): string {
  const data = (err as { data?: { message?: string } } | null)?.data
  return data?.message || fallback
}

function resetForms() {
  loginFormRef.value?.resetFields()
  registerFormRef.value?.resetFields()
  loginForm.password = ''
  registerForm.password = ''
  registerForm.confirm = ''
}

async function handleLogin() {
  const valid = await loginFormRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await auth.login(loginForm.username.trim(), loginForm.password)
    ElMessage.success(`欢迎回来，${auth.displayName.value}`)
    dialogVisible.value = false
  } catch (err) {
    ElMessage.error(errorMessage(err, '登录失败，请检查网络后重试'))
  } finally {
    submitting.value = false
  }
}

async function handleRegister() {
  const valid = await registerFormRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await auth.register({
      username: registerForm.username.trim(),
      email: registerForm.email.trim() || undefined,
      password: registerForm.password,
    })
    ElMessage.success('注册成功，已自动登录')
    dialogVisible.value = false
  } catch (err) {
    ElMessage.error(errorMessage(err, '注册失败，请稍后重试'))
  } finally {
    submitting.value = false
  }
}

// 关闭后清理，避免下次打开残留上次输入
watch(dialogVisible, (visible) => {
  if (!visible) resetForms()
})
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :width="420"
    align-center
    destroy-on-close
    class="auth-dialog"
    :show-close="true"
  >
    <template #header>
      <div class="auth-head">
        <div class="auth-head__mark">S</div>
        <div>
          <h2 class="auth-head__title">Study 基金</h2>
          <p class="auth-head__sub">登录后可关注基金、保存筛选条件</p>
        </div>
      </div>
    </template>

    <el-tabs v-model="dialogMode" class="auth-tabs" stretch>
      <el-tab-pane label="登录" name="login">
        <el-form
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          label-position="top"
          size="large"
          @submit.prevent="handleLogin"
        >
          <el-form-item label="用户名 / 邮箱" prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名或邮箱"
              autocomplete="username"
              clearable
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            class="auth-submit"
            :loading="submitting"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form>

        <p class="auth-switch">
          还没有账号？
          <button type="button" class="auth-switch__link" @click="dialogMode = 'register'">
            立即注册
          </button>
        </p>
      </el-tab-pane>

      <el-tab-pane label="注册" name="register">
        <el-form
          ref="registerFormRef"
          :model="registerForm"
          :rules="registerRules"
          label-position="top"
          size="large"
          @submit.prevent="handleRegister"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="registerForm.username"
              placeholder="字母、数字或下划线，3–50 位"
              autocomplete="username"
              clearable
            />
          </el-form-item>
          <el-form-item label="邮箱（可选）" prop="email">
            <el-input
              v-model="registerForm.email"
              placeholder="用于找回密码"
              autocomplete="email"
              clearable
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="registerForm.password"
              type="password"
              placeholder="至少 8 位"
              autocomplete="new-password"
              show-password
            />
          </el-form-item>
          <el-form-item label="确认密码" prop="confirm">
            <el-input
              v-model="registerForm.confirm"
              type="password"
              placeholder="再次输入密码"
              autocomplete="new-password"
              show-password
              @keyup.enter="handleRegister"
            />
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            class="auth-submit"
            :loading="submitting"
            @click="handleRegister"
          >
            注册并登录
          </el-button>
        </el-form>

        <p class="auth-switch">
          已有账号？
          <button type="button" class="auth-switch__link" @click="dialogMode = 'login'">
            去登录
          </button>
        </p>

        <p class="auth-note">注册即表示同意本站仅提供数据参考，不构成投资建议。</p>
      </el-tab-pane>
    </el-tabs>
  </el-dialog>
</template>

<style scoped>
.auth-head {
  display: flex;
  gap: 12px;
  align-items: center;
}

.auth-head__mark {
  display: grid;
  flex: none;
  place-items: center;
  width: 38px;
  height: 38px;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  background: var(--brand);
  border-radius: 11px;
}

.auth-head__title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--ink);
}

.auth-head__sub {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--muted);
}

.auth-tabs {
  margin-top: 4px;
}

.auth-submit {
  width: 100%;
  margin-top: 4px;
  font-weight: 600;
}

.auth-switch {
  margin: 16px 0 0;
  font-size: 13px;
  color: var(--muted);
  text-align: center;
}

.auth-switch__link {
  padding: 0;
  font-size: 13px;
  color: var(--brand);
  cursor: pointer;
  background: none;
  border: none;
}

.auth-switch__link:hover {
  text-decoration: underline;
}

.auth-note {
  margin: 12px 0 0;
  font-size: 11px;
  line-height: 1.7;
  color: var(--muted-2);
  text-align: center;
}

/* 让弹窗与站点圆角、品牌色一致 */
:deep(.el-dialog) {
  border-radius: 18px;
  box-shadow: var(--shadow-lg);
}

:deep(.el-dialog__header) {
  padding: 22px 24px 0;
  margin-right: 0;
}

:deep(.el-dialog__body) {
  padding: 16px 24px 24px;
}

:deep(.el-tabs__item) {
  font-weight: 600;
}

:deep(.el-form-item__label) {
  font-size: 13px;
  color: var(--ink-2);
}
</style>
