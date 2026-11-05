<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const form = reactive({
  // 仅开发环境预填，方便本地调试
  username: import.meta.env.DEV ? 'admin' : '',
  password: import.meta.env.DEV ? 'Admin@123456' : '',
})

const rules: FormRules<typeof form> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  try {
    await authStore.login({ ...form })
    ElMessage.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    await router.replace(redirect)
  } catch {
    // 失败提示已由 axios 拦截器统一处理
  }
}
</script>

<template>
  <div class="login">
    <div class="login__panel">
      <div class="login__brand">
        <div class="login__logo">S</div>
        <h1 class="login__title">拾贝 · 管理后台</h1>
        <p class="login__desc">
          前后端分离 · Vue 3 + Element Plus + FastAPI<br />
          统一鉴权、统一响应、可扩展的模块划分
        </p>
        <ul class="login__list">
          <li>用户 / 权限管理</li>
          <li>内容发布与门户同步</li>
          <li>接口自动生成文档</li>
        </ul>
      </div>

      <div class="login__form-wrap">
        <h2 class="login__form-title">账号登录</h2>
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          size="large"
          @submit.prevent="handleSubmit"
        >
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="请输入用户名或邮箱" clearable>
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              show-password
              @keyup.enter="handleSubmit"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-button
            type="primary"
            size="large"
            class="login__submit"
            :loading="authStore.loading"
            native-type="submit"
          >
            登 录
          </el-button>
        </el-form>

        <p class="login__hint">初始账号：admin / Admin@123456（由 <code>make seed</code> 生成）</p>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.login {
  display: grid;
  place-items: center;
  min-height: 100vh;
  padding: 24px;
  background: linear-gradient(135deg, #1f2937 0%, #2b6cb0 100%);

  &__panel {
    display: grid;
    grid-template-columns: 1fr 1fr;
    width: min(920px, 100%);
    overflow: hidden;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 24px 48px rgb(0 0 0 / 20%);
  }

  &__brand {
    display: flex;
    flex-direction: column;
    gap: 16px;
    justify-content: center;
    padding: 48px;
    color: #fff;
    background: linear-gradient(160deg, #2b6cb0 0%, #1f2937 100%);
  }

  &__logo {
    display: grid;
    place-items: center;
    width: 48px;
    height: 48px;
    font-size: 22px;
    font-weight: 700;
    background: rgb(255 255 255 / 15%);
    border-radius: 12px;
  }

  &__title {
    margin: 0;
    font-size: 26px;
  }

  &__desc {
    margin: 0;
    font-size: 13px;
    line-height: 1.8;
    opacity: 0.75;
  }

  &__list {
    margin: 8px 0 0;
    padding-left: 18px;
    font-size: 13px;
    line-height: 2;
    opacity: 0.85;
  }

  &__form-wrap {
    padding: 48px;
  }

  &__form-title {
    margin: 0 0 24px;
    font-size: 20px;
  }

  &__submit {
    width: 100%;
    margin-top: 8px;
  }

  &__hint {
    margin-top: 20px;
    font-size: 12px;
    color: $text-secondary;

    code {
      padding: 1px 4px;
      background: #eef2f7;
      border-radius: 4px;
    }
  }
}

@media (max-width: 720px) {
  .login__panel {
    grid-template-columns: 1fr;
  }

  .login__brand {
    display: none;
  }

  .login__form-wrap {
    padding: 32px 24px;
  }
}
</style>
