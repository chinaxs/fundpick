<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, formatDateTime, type User } from '@project/shared'

import { userApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { csvFilename, exportCsv } from '@/utils/export'

const authStore = useAuthStore()

const loading = ref(false)
const rows = ref<User[]>([])
const total = ref(0)
const selected = ref<User[]>([])
const batchSubmitting = ref(false)
const query = reactive({
  page: 1,
  page_size: DEFAULT_PAGE_SIZE,
  keyword: '',
  is_active: undefined as boolean | undefined,
})

const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const form = reactive({
  username: '',
  password: '',
  email: '',
  full_name: '',
  is_superuser: false,
  is_active: true,
})

const isEdit = computed(() => editingId.value !== null)

const rules = computed<FormRules<typeof form>>(() => ({
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: isEdit.value
    ? [{ min: 8, message: '密码至少 8 位', trigger: 'blur' }]
    : [
        { required: true, message: '请输入密码', trigger: 'blur' },
        { min: 8, message: '密码至少 8 位', trigger: 'blur' },
      ],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
}))

async function fetchList() {
  loading.value = true
  try {
    const result = await userApi.list({
      page: query.page,
      page_size: query.page_size,
      keyword: query.keyword || undefined,
      is_active: query.is_active,
    })
    rows.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  fetchList()
}

function resetQuery() {
  query.keyword = ''
  query.is_active = undefined
  query.page = 1
  fetchList()
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    username: '',
    password: '',
    email: '',
    full_name: '',
    is_superuser: false,
    is_active: true,
  })
  dialogVisible.value = true
}

function openEdit(row: User) {
  editingId.value = row.id
  Object.assign(form, {
    username: row.username,
    password: '',
    email: row.email ?? '',
    full_name: row.full_name ?? '',
    is_superuser: row.is_superuser,
    is_active: row.is_active,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEdit.value && editingId.value !== null) {
      await userApi.update(editingId.value, {
        email: form.email || null,
        full_name: form.full_name || null,
        is_superuser: form.is_superuser,
        is_active: form.is_active,
        ...(form.password ? { password: form.password } : {}),
      })
      ElMessage.success('已更新')
    } else {
      await userApi.create({
        username: form.username,
        password: form.password,
        email: form.email || null,
        full_name: form.full_name || null,
        is_superuser: form.is_superuser,
      })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await fetchList()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: User) {
  const confirmed = await ElMessageBox.confirm(`确定删除用户「${row.username}」吗？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).catch(() => false)
  if (!confirmed) return

  await userApi.remove(row.id)
  ElMessage.success('已删除')
  await fetchList()
}

async function handleBatchDelete() {
  const ids = selected.value.map((u) => u.id)
  const confirmed = await ElMessageBox.confirm(
    `确定删除选中的 ${ids.length} 个用户吗？当前登录账号会被自动跳过。`,
    '批量删除',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) return

  batchSubmitting.value = true
  try {
    const { affected } = await userApi.batchRemove(ids)
    ElMessage.success(`已删除 ${affected} 个用户`)
    selected.value = []
    await fetchList()
  } finally {
    batchSubmitting.value = false
  }
}

function handleExport() {
  exportCsv(csvFilename('users'), rows.value, [
    { header: 'ID', value: (u) => u.id },
    { header: '用户名', value: (u) => u.username },
    { header: '姓名', value: (u) => u.full_name },
    { header: '邮箱', value: (u) => u.email },
    { header: '角色', value: (u) => (u.is_superuser ? '超级管理员' : '普通用户') },
    { header: '状态', value: (u) => (u.is_active ? '启用' : '禁用') },
    { header: '创建时间', value: (u) => formatDateTime(u.created_at) },
  ])
  ElMessage.success(`已导出当前页 ${rows.value.length} 条`)
}

/** 自己的行不可勾选：后端也会再拦一道，这里是交互层提示 */
function canSelect(row: User): boolean {
  return row.id !== authStore.currentUser?.id
}

onMounted(fetchList)
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h2 class="page__title">用户管理</h2>
      <div class="header-actions">
        <el-button :disabled="!rows.length" @click="handleExport">
          <el-icon><Download /></el-icon>导出 CSV
        </el-button>
        <el-button
          type="danger"
          plain
          :disabled="!selected.length"
          :loading="batchSubmitting"
          @click="handleBatchDelete"
        >
          批量删除{{ selected.length ? `（${selected.length}）` : '' }}
        </el-button>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>新建用户
        </el-button>
      </div>
    </div>

    <div class="card">
      <div class="filter-bar">
        <el-input
          v-model="query.keyword"
          placeholder="用户名 / 邮箱"
          clearable
          style="width: 220px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-select
          v-model="query.is_active"
          placeholder="状态"
          clearable
          style="width: 140px"
          @change="handleSearch"
        >
          <el-option label="启用" :value="true" />
          <el-option label="禁用" :value="false" />
        </el-select>
        <el-button type="primary" plain @click="handleSearch">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="rows"
        stripe
        border
        @selection-change="(vals: User[]) => (selected = vals)"
      >
        <el-table-column type="selection" width="44" :selectable="canSelect" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="full_name" label="姓名" min-width="120">
          <template #default="{ row }">{{ row.full_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="200">
          <template #default="{ row }">{{ row.email || '—' }}</template>
        </el-table-column>
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-tag :type="row.is_superuser ? 'danger' : 'info'" size="small">
              {{ row.is_superuser ? '管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row as User)"
              >编辑</el-button
            >
            <el-button link type="danger" size="small" @click="handleDelete(row as User)"
              >删除</el-button
            >
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[...PAGE_SIZE_OPTIONS]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="fetchList"
        />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新建用户'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEdit" placeholder="登录名，唯一" />
        </el-form-item>
        <el-form-item :label="isEdit ? '重置密码' : '密码'" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="isEdit ? '留空则不修改' : '至少 8 位'"
          />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="选填" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.full_name" placeholder="选填" />
        </el-form-item>
        <el-form-item label="超级管理员">
          <el-switch v-model="form.is_superuser" />
        </el-form-item>
        <el-form-item v-if="isEdit" label="启用状态">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.header-actions {
  display: flex;
  gap: 12px;
}
</style>
