<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'

const { user, isLoggedIn, displayName, avatarText, openAuth, ensureSession, fetchProfile, logout } =
  useAuth()
await ensureSession()

const { count: favCount, reset: resetFavorites } = useFavorites()
const router = useRouter()

const profileForm = reactive({ full_name: '', email: '', avatar_url: '' })
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })
const savingProfile = ref(false)
const savingPassword = ref(false)

watch(
  user,
  (value) => {
    if (!value) return
    profileForm.full_name = value.full_name ?? ''
    profileForm.email = value.email ?? ''
    profileForm.avatar_url = value.avatar_url ?? ''
  },
  { immediate: true },
)

function dateText(value: string | null | undefined): string {
  if (!value) return '—'
  return value.replace('T', ' ').slice(0, 16)
}

async function saveProfile() {
  savingProfile.value = true
  try {
    await updateMyProfile({
      full_name: profileForm.full_name.trim() || null,
      email: profileForm.email.trim() || null,
      avatar_url: profileForm.avatar_url.trim() || null,
    })
    await fetchProfile()
    ElMessage.success('资料已保存')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败，请稍后重试')
  } finally {
    savingProfile.value = false
  }
}

async function savePassword() {
  if (pwdForm.new_password.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (pwdForm.new_password !== pwdForm.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  savingPassword.value = true
  try {
    await changeMyPassword(pwdForm.old_password, pwdForm.new_password)
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm_password = ''
    ElMessage.success('密码已更新，下次登录请使用新密码')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '修改失败，请检查原密码')
  } finally {
    savingPassword.value = false
  }
}

async function doLogout() {
  await logout()
  resetFavorites()
  ElMessage.success('已退出登录')
  await router.push('/')
}

async function doDeactivate() {
  try {
    const { value } = await ElMessageBox.prompt(
      '注销后账号将无法登录，关注列表也会被清空。请输入当前密码确认：',
      '注销账号',
      {
        confirmButtonText: '确认注销',
        cancelButtonText: '取消',
        inputType: 'password',
        inputPlaceholder: '当前登录密码',
        confirmButtonClass: 'el-button--danger',
      },
    )
    if (!value) return
    await deactivateMyAccount(value)
    await logout()
    resetFavorites()
    ElMessage.success('账号已注销')
    await router.push('/')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error instanceof Error ? error.message : '注销失败')
  }
}

useSeoMeta({
  title: '个人中心',
  description: '管理拾贝账号资料、登录密码与账号安全设置。',
})
</script>

<template>
  <div class="page">
    <div class="container">
      <header class="head">
        <div>
          <p class="section__eyebrow">Account</p>
          <h1 class="head__title">个人中心</h1>
          <p class="head__sub">管理账号资料与安全设置</p>
        </div>
        <NuxtLink v-if="isLoggedIn" to="/dashboard" class="link-more">前往工作台 →</NuxtLink>
      </header>

      <section v-if="!isLoggedIn" class="empty">
        <div class="empty__icon">◎</div>
        <h2 class="empty__title">还没有登录</h2>
        <p class="empty__desc">登录后可以修改资料、管理密码和账号安全。</p>
        <button type="button" class="btn btn--primary" @click="openAuth('login')">
          登录 / 注册
        </button>
      </section>

      <div v-else class="layout">
        <!-- 左：账号概览 -->
        <aside class="side">
          <div class="card profile-card">
            <div class="avatar">{{ avatarText }}</div>
            <div class="profile-card__name">{{ displayName }}</div>
            <div class="profile-card__user num">@{{ user?.username }}</div>
            <div class="profile-card__divider" />
            <dl class="meta">
              <div class="meta__row">
                <dt>注册时间</dt>
                <dd class="num">{{ dateText(user?.created_at) }}</dd>
              </div>
              <div class="meta__row">
                <dt>最近登录</dt>
                <dd class="num">{{ dateText(user?.last_login_at) }}</dd>
              </div>
              <div class="meta__row">
                <dt>关注基金</dt>
                <dd class="num">{{ favCount }} 只</dd>
              </div>
            </dl>
          </div>

          <nav class="card side__nav">
            <NuxtLink to="/dashboard" class="side__link">▤ 我的工作台</NuxtLink>
            <NuxtLink to="/favorites" class="side__link">☆ 我的关注</NuxtLink>
            <NuxtLink to="/positions" class="side__link">◈ 模拟持仓</NuxtLink>
            <NuxtLink to="/funds" class="side__link">⌕ 基金筛选</NuxtLink>
          </nav>
        </aside>

        <!-- 右：设置 -->
        <div class="main">
          <section class="card block">
            <div class="block__head">
              <div>
                <h2 class="block__title">基本资料</h2>
                <p class="block__sub">用户名是登录凭证，注册后不可修改</p>
              </div>
            </div>

            <div class="form">
              <label class="field">
                <span class="field__label">用户名</span>
                <input :value="user?.username" class="input" disabled />
              </label>

              <label class="field">
                <span class="field__label">显示名称</span>
                <input
                  v-model="profileForm.full_name"
                  class="input"
                  maxlength="50"
                  placeholder="用于页面展示的昵称"
                />
              </label>

              <label class="field">
                <span class="field__label">邮箱</span>
                <input
                  v-model="profileForm.email"
                  class="input"
                  type="email"
                  placeholder="可用于登录与找回账号"
                />
              </label>

              <label class="field">
                <span class="field__label">头像地址</span>
                <input
                  v-model="profileForm.avatar_url"
                  class="input"
                  placeholder="https://…（留空则使用首字母头像）"
                />
              </label>

              <div class="form__foot">
                <button
                  type="button"
                  class="btn btn--primary"
                  :disabled="savingProfile"
                  @click="saveProfile"
                >
                  {{ savingProfile ? '保存中…' : '保存资料' }}
                </button>
              </div>
            </div>
          </section>

          <section class="card block">
            <div class="block__head">
              <div>
                <h2 class="block__title">修改密码</h2>
                <p class="block__sub">修改后其他设备上的登录状态不会立即失效</p>
              </div>
            </div>

            <div class="form">
              <label class="field">
                <span class="field__label">原密码</span>
                <input
                  v-model="pwdForm.old_password"
                  class="input"
                  type="password"
                  autocomplete="current-password"
                  placeholder="当前登录密码"
                />
              </label>
              <label class="field">
                <span class="field__label">新密码</span>
                <input
                  v-model="pwdForm.new_password"
                  class="input"
                  type="password"
                  autocomplete="new-password"
                  placeholder="至少 8 位"
                />
              </label>
              <label class="field">
                <span class="field__label">确认新密码</span>
                <input
                  v-model="pwdForm.confirm_password"
                  class="input"
                  type="password"
                  autocomplete="new-password"
                  placeholder="再输入一次新密码"
                />
              </label>

              <div class="form__foot">
                <button
                  type="button"
                  class="btn btn--primary"
                  :disabled="savingPassword"
                  @click="savePassword"
                >
                  {{ savingPassword ? '提交中…' : '更新密码' }}
                </button>
              </div>
            </div>
          </section>

          <section class="card block block--danger">
            <div class="block__head">
              <div>
                <h2 class="block__title">账号安全</h2>
                <p class="block__sub">退出当前设备，或永久注销账号</p>
              </div>
            </div>

            <div class="danger-rows">
              <div class="danger-row">
                <div>
                  <div class="danger-row__title">退出登录</div>
                  <div class="danger-row__desc">清除本设备的登录凭证</div>
                </div>
                <button type="button" class="btn" @click="doLogout">退出</button>
              </div>
              <div class="danger-row">
                <div>
                  <div class="danger-row__title">注销账号</div>
                  <div class="danger-row__desc">软删除账号并清空关注列表，操作不可撤销</div>
                </div>
                <button type="button" class="btn btn--danger" @click="doDeactivate">注销</button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 40px 0 56px;
}

.head {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-end;
  justify-content: space-between;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--line-soft);
}

.head__title {
  margin: 6px 0 0;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.head__sub {
  margin: 9px 0 0;
  font-size: 13.5px;
  color: var(--muted);
}

.link-more {
  font-size: 13px;
  color: var(--brand);
}

.layout {
  display: grid;
  grid-template-columns: 268px minmax(0, 1fr);
  gap: 18px;
  margin-top: 24px;
  align-items: start;
}

.side {
  display: grid;
  gap: 14px;
}

.profile-card {
  padding: 26px 22px;
  text-align: center;
}

.avatar {
  display: flex;
  width: 66px;
  height: 66px;
  margin: 0 auto;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, var(--brand), #7c3aed);
  border-radius: 20px;
}

.profile-card__name {
  margin-top: 14px;
  font-size: 17px;
  font-weight: 600;
}

.profile-card__user {
  margin-top: 3px;
  font-size: 12px;
  color: var(--muted-2);
}

.profile-card__divider {
  height: 1px;
  margin: 20px 0 14px;
  background: var(--line-soft);
}

.meta {
  display: grid;
  gap: 10px;
  margin: 0;
}

.meta__row {
  display: flex;
  gap: 10px;
  align-items: baseline;
  justify-content: space-between;
  font-size: 12px;
}

.meta dt {
  color: var(--muted-2);
}

.meta dd {
  margin: 0;
  color: var(--ink-2);
}

.side__nav {
  display: grid;
  padding: 8px;
}

.side__link {
  padding: 10px 12px;
  font-size: 13px;
  color: var(--ink-2);
  border-radius: 8px;
}

.side__link:hover {
  color: var(--brand);
  background: var(--bg-soft);
}

.main {
  display: grid;
  gap: 16px;
}

.block {
  padding: 22px 24px;
}

.block__head {
  padding-bottom: 14px;
  margin-bottom: 18px;
  border-bottom: 1px solid var(--line-soft);
}

.block__title {
  margin: 0;
  font-size: 15.5px;
  font-weight: 600;
}

.block__sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--muted);
}

/* 表单 */
.form {
  display: grid;
  gap: 14px;
}

.field {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
}

.field__label {
  font-size: 13px;
  color: var(--muted);
}

.input {
  width: 100%;
  height: 38px;
  padding: 0 12px;
  font-size: 13.5px;
  color: var(--ink);
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 8px;
  outline: none;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.input:focus {
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgb(59 130 246 / 12%);
}

.input:disabled {
  color: var(--muted);
  background: var(--bg-soft);
  cursor: not-allowed;
}

.form__foot {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
}

/* 危险操作 */
.block--danger {
  border-color: #fecaca;
}

.danger-rows {
  display: grid;
  gap: 4px;
}

.danger-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid var(--line-soft);
}

.danger-row:last-child {
  border-bottom: none;
}

.danger-row__title {
  font-size: 13.5px;
  font-weight: 500;
}

.danger-row__desc {
  margin-top: 3px;
  font-size: 12px;
  color: var(--muted-2);
}

.btn--danger {
  color: #dc2626;
  border-color: #fecaca;
}

.btn--danger:hover {
  background: #fef2f2;
}

/* 空态 */
.empty {
  padding: 72px 24px;
  margin-top: 24px;
  text-align: center;
  background: var(--bg-soft);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

.empty__icon {
  font-size: 34px;
  color: #cbd5e1;
}

.empty__title {
  margin-top: 8px;
  font-size: 17px;
  font-weight: 600;
}

.empty__desc {
  margin: 8px 0 22px;
  font-size: 13.5px;
  color: var(--muted);
}

@media (max-width: 860px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .side {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 560px) {
  .side {
    grid-template-columns: 1fr;
  }

  .field {
    grid-template-columns: 1fr;
    gap: 5px;
  }

  .head__title {
    font-size: 25px;
  }
}
</style>
