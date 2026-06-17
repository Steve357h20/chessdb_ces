<template>
  <div class="aa-root">
    <div class="aa-toolbar">
      <el-radio-group v-model="status" size="small" @change="loadModRequests">
        <el-radio-button value="pending">待审核</el-radio-button>
        <el-radio-button value="approved">已通过</el-radio-button>
        <el-radio-button value="rejected">已拒绝</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="modRequests" v-loading="loadingMod" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="申请人" width="120">
        <template #default="{ row }">{{ row.applicant_name }}</template>
      </el-table-column>
      <el-table-column label="资源类型" width="100">
        <template #default="{ row }">
          <el-tag size="small">{{ targetTypeLabel(row.target_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-tag :type="actionTagType(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="目标 ID" prop="target_id" width="80" />
      <el-table-column label="申请理由" prop="reason" show-overflow-tooltip />
      <el-table-column label="提交时间" width="160">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'" size="small" type="success" @click="openReview(row, 'approve')">通过</el-button>
          <el-button v-if="row.status === 'pending'" size="small" type="danger" @click="openReview(row, 'reject')">拒绝</el-button>
          <el-button size="small" text @click="viewPayload(row)">查看详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loadingMod && modRequests.length === 0" description="暂无申请" />

    <!-- 审核对话框 -->
    <el-dialog v-model="reviewDialog" :title="reviewAction === 'approve' ? '通过申请' : '拒绝申请'" width="500px">
      <p>申请人：<b>{{ reviewing?.applicant_name }}</b></p>
      <p>资源：{{ targetTypeLabel(reviewing?.target_type) }} #{{ reviewing?.target_id }}</p>
      <p>操作：{{ actionLabel(reviewing?.action) }}</p>
      <p>理由：{{ reviewing?.reason || '（无）' }}</p>
      <el-input v-model="reviewComment" type="textarea" :rows="3" placeholder="审核意见" />
      <template #footer>
        <el-button @click="reviewDialog = false">取消</el-button>
        <el-button :type="reviewAction === 'approve' ? 'success' : 'danger'" @click="confirmReview">
          确认{{ reviewAction === 'approve' ? '通过' : '拒绝' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Payload 详情对话框 -->
    <el-dialog v-model="payloadDialog" title="申请详情" width="600px">
      <pre class="aa-payload">{{ payloadText }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listModRequests, reviewModRequest, getModRequest } from '@/api/admin'

const status = ref('pending')
const modRequests = ref([])
const loadingMod = ref(false)
const reviewDialog = ref(false)
const reviewAction = ref('approve')
const reviewing = ref(null)
const reviewComment = ref('')
const payloadDialog = ref(false)
const payloadText = ref('')

function targetTypeLabel(t) {
  return { game: '棋谱', puzzle: '残局', collection: '收藏', profile: '账号', player: '棋手' }[t] || t
}
function actionLabel(a) { return { create: '创建', update: '更新', delete: '删除' }[a] || a }
function actionTagType(a) { return { create: 'success', update: 'warning', delete: 'danger' }[a] || '' }
function statusLabel(s) { return { pending: '待审核', approved: '已通过', rejected: '已拒绝' }[s] || s }
function statusTagType(s) { return { pending: 'warning', approved: 'success', rejected: 'danger' }[s] || '' }
function formatTime(iso) { return iso ? new Date(iso).toLocaleString('zh-CN') : '-' }

async function loadModRequests() {
  loadingMod.value = true
  try {
    const res = await listModRequests({ status: status.value })
    modRequests.value = (res.data || res).requests || []
  } catch {
    modRequests.value = []
  } finally {
    loadingMod.value = false
  }
}

function openReview(row, action) {
  reviewing.value = row
  reviewAction.value = action
  reviewComment.value = ''
  reviewDialog.value = true
}

async function confirmReview() {
  try {
    await reviewModRequest(reviewing.value.id, { action: reviewAction.value, comment: reviewComment.value })
    ElMessage.success('审核完成')
    reviewDialog.value = false
    await loadModRequests()
  } catch (e) {
    ElMessage.error('审核失败: ' + (e.message || ''))
  }
}

async function viewPayload(row) {
  try {
    const res = await getModRequest(row.id)
    payloadText.value = JSON.stringify(res.data || res, null, 2)
  } catch {
    payloadText.value = JSON.stringify(row, null, 2)
  }
  payloadDialog.value = true
}

function onRefresh() { loadModRequests() }

onMounted(() => {
  loadModRequests()
  window.addEventListener('admin-refresh', onRefresh)
})
</script>

<style scoped>
.aa-toolbar { margin-bottom: 12px; }
.aa-payload {
  background: var(--bg-color-tertiary); color: var(--text-color-regular); padding: 12px; border-radius: 4px;
  font-size: 12px; max-height: 400px; overflow: auto;
}
</style>
