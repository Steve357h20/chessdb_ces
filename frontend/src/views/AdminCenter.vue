<template>
  <div class="admin-center">
    <div class="ac-header">
      <h2>
        <el-icon><Setting /></el-icon>
        管理中心
      </h2>
      <div class="ac-header-right">
        <span class="ac-role">当前角色：管理员 {{ user?.username }}</span>
        <el-button size="small" :icon="Refresh" @click="refreshAll">刷新</el-button>
      </div>
    </div>

    <el-container class="ac-body">
      <el-aside class="ac-aside" width="220px">
        <el-menu
          :default-active="activeMenu"
          class="ac-menu"
          router
        >
          <el-menu-item index="/admin/center/overview">
            <el-icon><DataLine /></el-icon>
            <span>运营总览</span>
          </el-menu-item>
          <el-menu-item index="/admin/center/traffic">
            <el-icon><TrendCharts /></el-icon>
            <span>API 流量分析</span>
          </el-menu-item>
          <el-menu-item index="/admin/center/audit">
            <el-icon><Document /></el-icon>
            <span>申请审核</span>
            <el-badge
              v-if="pendingCount > 0"
              :value="pendingCount"
              class="ac-menu-badge"
              type="warning"
            />
          </el-menu-item>
          <el-menu-item index="/admin/center/users">
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="ac-main">
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { Setting, Refresh, DataLine, TrendCharts, Document, User } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/userStore'
import { listModRequests } from '@/api/admin'

const route = useRoute()
const userStore = useUserStore()
const user = userStore.user

const pendingCount = ref(0)
let timer = null

const activeMenu = computed(() => route.path)

async function loadPendingCount() {
  try {
    const res = await listModRequests({ status: 'pending' })
    const data = res.data || res
    pendingCount.value = (data.requests || []).length
  } catch {
    pendingCount.value = 0
  }
}

function refreshAll() {
  // 子组件内 watch route 不会触发，所以这里 dispatch 一个全局事件
  window.dispatchEvent(new CustomEvent('admin-refresh'))
  loadPendingCount()
}

onMounted(() => {
  loadPendingCount()
  // 30s 轮询待审核数
  timer = setInterval(loadPendingCount, 30000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.admin-center { padding: 16px; height: 100%; box-sizing: border-box; background: var(--bg-color); color: var(--text-color); }
.ac-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.ac-header h2 { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--text-color); }
.ac-header-right { display: flex; align-items: center; gap: 12px; }
.ac-role { color: var(--text-color-secondary); font-size: 13px; }
.ac-body { background: var(--card-bg); border-radius: 6px; min-height: 600px; }
.ac-aside { background: var(--sidebar-bg); border-right: 1px solid var(--border-color-lighter); }
.ac-menu { border-right: none; background: transparent; }
.ac-menu-badge { margin-left: auto; }
.ac-main { padding: 20px; background: var(--card-bg); }
</style>
