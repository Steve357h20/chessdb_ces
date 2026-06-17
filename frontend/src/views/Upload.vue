<template>
  <div class="upload-page">
    <div class="up-header">
      <h1>上传棋谱</h1>
      <p class="up-desc">支持 PGN 格式文件上传，系统将自动解析对局信息</p>
    </div>

    <el-card class="up-card">
      <el-upload
        ref="uploadRef"
        class="up-upload"
        drag
        action=""
        :auto-upload="false"
        :on-change="onFileChange"
        :on-remove="onFileRemove"
        accept=".pgn"
        multiple
      >
        <el-icon class="el-icon--upload"><Upload /></el-icon>
        <div class="el-upload__text">
          拖拽 PGN 文件到此处，或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">仅支持 .pgn 格式文件，可同时上传多个文件</div>
        </template>
      </el-upload>

      <div class="up-actions">
        <el-button
          type="primary"
          :loading="uploading"
          :disabled="fileList.length === 0"
          @click="onUpload"
        >{{ uploading ? '上传中...' : '开始上传' }}</el-button>
        <el-button @click="clearFiles">清空文件</el-button>
      </div>

      <div v-if="results.length" class="up-results">
        <h3>上传结果</h3>
        <div
          v-for="(r, i) in results"
          :key="i"
          class="up-result-item"
          :class="{ 'up-result-success': r.success, 'up-result-error': !r.success }"
        >
          <el-icon v-if="r.success" color="#67c23a"><CircleCheck /></el-icon>
          <el-icon v-else color="#f56c6c"><CircleClose /></el-icon>
          <span>{{ r.filename }}: {{ r.message }}</span>
        </div>
      </div>

      <div class="up-paste">
        <h3>或直接粘贴 PGN 内容</h3>
        <el-input
          v-model="pgnText"
          type="textarea"
          :rows="8"
          placeholder="[Event &quot;...&quot;]&#10;[Site &quot;...&quot;]&#10;[Date &quot;...&quot;]&#10;[White &quot;...&quot;]&#10;[Black &quot;...&quot;]&#10;[Result &quot;...&quot;]&#10;&#10;1. e4 e5 2. Nf3 Nc6 ..."
        />
        <el-button
          type="primary"
          :loading="pasting"
          :disabled="!pgnText.trim()"
          style="margin-top: 12px"
          @click="onPasteSubmit"
        >提交 PGN</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Upload, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { uploadGames } from '@/api/games'
import request from '@/api/request'

const router = useRouter()

const uploadRef = ref(null)
const fileList = ref([])
const uploading = ref(false)
const pasting = ref(false)
const results = ref([])
const pgnText = ref('')

function onFileChange(file) {
  fileList.value.push(file)
}

function onFileRemove(file) {
  const idx = fileList.value.findIndex(f => f.uid === file.uid)
  if (idx !== -1) fileList.value.splice(idx, 1)
}

function clearFiles() {
  fileList.value = []
  if (uploadRef.value) uploadRef.value.clearFiles()
}

async function onUpload() {
  if (fileList.value.length === 0) return
  uploading.value = true
  results.value = []

  try {
    const rawFiles = fileList.value.map(f => f.raw)
    const res = await uploadGames(rawFiles)
    const data = res.data || res

    // 普通用户走审核流程
    if (data.need_review) {
      results.value = [{
        filename: '上传申请',
        success: true,
        message: data.message || `已提交 ${data.submitted} 条上传申请，等待管理员审核`,
      }]
      ElMessage.info(data.message || '已提交申请，等待审核')
      clearFiles()
      return
    }

    if (data.results && Array.isArray(data.results)) {
      results.value = data.results.map(r => ({
        filename: r.filename || r.event || '未知',
        success: r.success !== false,
        message: r.message || r.error || '上传成功',
      }))
    } else {
      results.value = [{
        filename: '批量上传',
        success: true,
        message: `成功导入 ${data.imported || data.count || data.uploaded || fileList.value.length} 局对局`,
      }]
    }

    ElMessage.success('上传完成')
    clearFiles()
  } catch (e) {
    results.value = [{
      filename: '上传失败',
      success: false,
      message: e.message || '上传出错',
    }]
  } finally {
    uploading.value = false
  }
}

async function onPasteSubmit() {
  if (!pgnText.value.trim()) return
  pasting.value = true
  try {
    const res = await request.post('/games/upload-pgn', { pgn: pgnText.value })
    const data = res.data || res
    if (data.need_review) {
      ElMessage.info(data.message || '已提交上传申请，等待管理员审核')
    } else {
      ElMessage.success(`成功导入 ${data.imported || data.count || 1} 局对局`)
    }
    pgnText.value = ''
  } catch (e) {
    ElMessage.error('PGN 解析失败：' + (e.message || '格式错误'))
  } finally {
    pasting.value = false
  }
}
</script>

<style scoped>
.upload-page {
  max-width: 700px;
  margin: 0 auto;
}

.up-header {
  margin-bottom: 20px;
}

.up-header h1 {
  font-size: 24px;
  color: var(--text-color);
  margin: 0 0 8px;
}

.up-desc {
  color: var(--text-color-secondary);
  font-size: 14px;
  margin: 0;
}

.up-card {
  padding: 8px;
}

.up-upload {
  margin-bottom: 16px;
}

.up-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.up-results {
  margin-bottom: 24px;
}

.up-results h3 {
  font-size: 14px;
  color: var(--text-color);
  margin: 0 0 12px;
}

.up-result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
  margin-bottom: 6px;
}

.up-result-success {
  background: #f0f9eb;
  color: #67c23a;
}

.up-result-error {
  background: #fef0f0;
  color: #f56c6c;
}

.up-paste {
  border-top: 1px solid var(--border-color-lighter);
  padding-top: 20px;
}

.up-paste h3 {
  font-size: 14px;
  color: var(--text-color);
  margin: 0 0 12px;
}
</style>
