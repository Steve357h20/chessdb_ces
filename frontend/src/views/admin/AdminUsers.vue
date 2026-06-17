<template>
  <div class="au-root">
    <div class="au-toolbar">
      <el-input
        v-model="userQuery"
        placeholder="搜索 username / email"
        style="width: 280px"
        clearable
        @clear="loadUsers"
        @keyup.enter="loadUsers"
      >
        <template #append>
          <el-button @click="loadUsers">搜索</el-button>
        </template>
      </el-input>
      <span style="margin-left: 16px; color: #909399">共 {{ usersTotal }} 位用户</span>
    </div>

    <el-table :data="users" v-loading="loadingUsers" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="email" label="邮箱" width="200" show-overflow-tooltip />
      <el-table-column label="角色" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.is_admin" type="danger" size="small">管理员</el-tag>
          <el-tag v-else type="info" size="small">普通用户</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="收藏" prop="collections_count" width="80" />
      <el-table-column label="浏览" prop="browsing_count" width="80" />
      <el-table-column label="申请" prop="mod_requests_count" width="80" />
      <el-table-column label="24h API" prop="api_calls_24h" width="100" />
      <el-table-column label="注册时间" width="160">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openEditUser(row)">编辑</el-button>
          <el-button size="small" text @click="openResetPwd(row)">重置密码</el-button>
          <el-button size="small" text type="danger" :disabled="row.id === user?.id" @click="confirmDeleteUser(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="userPage"
      :page-size="userPerPage"
      :total="usersTotal"
      layout="prev, pager, next, total"
      style="margin-top: 12px; justify-content: flex-end"
      @current-change="loadUsers"
    />

    <el-dialog v-model="editUserDialog" title="编辑用户" width="500px">
      <el-form :model="editUserForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="editUserForm.username" disabled />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editUserForm.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-switch
            v-model="editUserForm.is_admin"
            active-text="管理员"
            inactive-text="普通用户"
            inline-prompt
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editUserDialog = false">取消</el-button>
        <el-button type="primary" @click="submitEditUser">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetPwdDialog" :title="`重置 ${resetPwdUser?.username} 的密码`" width="420px">
      <el-input v-model="newPwd" placeholder="新密码（6-128 字符）" show-password />
      <template #footer>
        <el-button @click="resetPwdDialog = false">取消</el-button>
        <el-button type="primary" @click="submitResetPwd">重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/store/userStore'
import { listAdminUsers, updateAdminUser, resetAdminUserPassword, deleteAdminUser } from '@/api/admin'

const userStore = useUserStore()
const user = userStore.user

const users = ref([])
const usersTotal = ref(0)
const loadingUsers = ref(false)
const userQuery = ref('')
const userPage = ref(1)
const userPerPage = ref(20)

const editUserDialog = ref(false)
const editUserForm = ref({ id: null, username: '', email: '', is_admin: false })
const resetPwdDialog = ref(false)
const resetPwdUser = ref(null)
const newPwd = ref('')

function formatTime(iso) { return iso ? new Date(iso).toLocaleString('zh-CN') : '-' }

async function loadUsers() {
  loadingUsers.value = true
  try {
    const res = await listAdminUsers({
      page: userPage.value,
      per_page: userPerPage.value,
      q: userQuery.value,
    })
    const data = res.data || res
    users.value = data.items || []
    usersTotal.value = data.total || 0
  } catch {
    users.value = []
  } finally {
    loadingUsers.value = false
  }
}

function openEditUser(row) {
  editUserForm.value = { id: row.id, username: row.username, email: row.email, is_admin: row.is_admin }
  editUserDialog.value = true
}

async function submitEditUser() {
  try {
    await updateAdminUser(editUserForm.value.id, {
      email: editUserForm.value.email,
      is_admin: editUserForm.value.is_admin,
    })
    ElMessage.success('已保存')
    editUserDialog.value = false
    await loadUsers()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || ''))
  }
}

function openResetPwd(row) {
  resetPwdUser.value = row
  newPwd.value = ''
  resetPwdDialog.value = true
}

async function submitResetPwd() {
  if (!newPwd.value || newPwd.value.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  try {
    await resetAdminUserPassword(resetPwdUser.value.id, newPwd.value)
    ElMessage.success('已重置')
    resetPwdDialog.value = false
  } catch (e) {
    ElMessage.error('重置失败: ' + (e.message || ''))
  }
}

async function confirmDeleteUser(row) {
  try {
    await ElMessageBox.confirm(`确认删除用户 ${row.username}？此操作将级联清理其收藏/浏览/审核记录。`, '确认', { type: 'warning' })
  } catch { return }
  try {
    await deleteAdminUser(row.id)
    ElMessage.success('已删除')
    await loadUsers()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.message || ''))
  }
}

function onRefresh() { loadUsers() }

onMounted(() => {
  loadUsers()
  window.addEventListener('admin-refresh', onRefresh)
})
</script>

<style scoped>
.au-toolbar { margin-bottom: 12px; display: flex; align-items: center; }
.au-toolbar span { color: var(--text-color-secondary); }
</style>
