<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { formatDateTime, type StaffUser } from '@project/shared'

import { authApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

/** 个人设置：资料只读展示（改资料走后台账号管理），密码可自助修改 */
const authStore = useAuthStore()
const router = useRouter()
const profile = ref<StaffUser | null>(null)
const profileLoading = ref(true)

const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const rules: FormRules<typeof form> = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 64, message: '长度 8-64 个字符', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        if (value !== form.new_password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

async function fetchProfile() {
  profileLoading.value = true
  try {
    profile.value = await authApi.me()
  } finally {
    profileLoading.value = false
  }
}

async function handleChangePassword() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await authApi.changePassword({
      old_password: form.old_password,
      new_password: form.new_password,
    })
    await authStore.logout()
    ElMessage.success('密码已修改，请重新登录')
    formRef.value?.resetFields()
    await router.replace({ name: 'login' })
  } finally {
    submitting.value = false
  }
}

onMounted(fetchProfile)
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">个人设置</h2>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="10">
        <div class="card">
          <h3 class="section-title">账号资料</h3>
          <el-skeleton v-if="profileLoading" :rows="5" animated />
          <template v-else>
            <div class="profile">
              <el-avatar :size="64" class="profile__avatar">
                {{ authStore.displayName.slice(0, 1) }}
              </el-avatar>
              <div class="profile__info">
                <div class="profile__name">{{ authStore.displayName }}</div>
                <div class="muted">{{ profile?.email ?? '未设置邮箱' }}</div>
              </div>
            </div>
            <el-descriptions :column="1" border style="margin-top: 16px">
              <el-descriptions-item label="用户名">{{ profile?.username }}</el-descriptions-item>
              <el-descriptions-item label="姓名">
                {{ profile?.full_name ?? '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="角色">
                <el-tag v-if="profile?.is_superuser" type="danger" size="small">超级管理员</el-tag>
                <el-tag v-else type="warning" size="small">员工</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="注册时间">
                {{ formatDateTime(profile?.created_at) }}
              </el-descriptions-item>
            </el-descriptions>
          </template>
        </div>
      </el-col>

      <el-col :xs="24" :lg="14">
        <div class="card">
          <h3 class="section-title">修改密码</h3>
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="110px"
            style="max-width: 460px"
          >
            <el-form-item label="当前密码" prop="old_password">
              <el-input
                v-model="form.old_password"
                type="password"
                show-password
                autocomplete="current-password"
              />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input
                v-model="form.new_password"
                type="password"
                show-password
                autocomplete="new-password"
                placeholder="8-64 位，建议字母 + 数字组合"
              />
            </el-form-item>
            <el-form-item label="确认新密码" prop="confirm_password">
              <el-input
                v-model="form.confirm_password"
                type="password"
                show-password
                autocomplete="new-password"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="handleChangePassword">
                确认修改
              </el-button>
            </el-form-item>
          </el-form>
          <el-alert
            type="warning"
            :closable="false"
            show-icon
            title="修改密码后当前登录态保持有效，其他设备的登录态将在 token 过期后失效"
          />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.muted {
  font-size: 13px;
  color: $text-secondary;
}

.section-title {
  margin: 0 0 16px;
  font-size: 15px;
  font-weight: 600;
}

.profile {
  display: flex;
  gap: 16px;
  align-items: center;

  &__avatar {
    flex: none;
    font-size: 24px;
    font-weight: 600;
    color: #fff;
    background: $color-primary;
  }

  &__name {
    font-size: 18px;
    font-weight: 600;
  }
}
</style>
