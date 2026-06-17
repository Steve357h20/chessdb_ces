<template>
  <div class="puzzle-library-page">
    <div class="pl-header">
      <h2>残局库</h2>
      <div class="pl-header-right">
        <div v-if="filterSourceGameId" class="pl-filter-hint">
          <span>筛选：来源对局 #{{ filterSourceGameId }} 的残局</span>
          <el-button size="small" text type="primary" @click="clearSourceFilter">清除筛选</el-button>
        </div>
        <div class="pl-header-hint">
          <el-icon><InfoFilled /></el-icon>
          在棋谱详细页点击「截取残局」可将局面加入残局库
        </div>
      </div>
    </div>

    <div class="pl-filters">
      <el-select v-model="filterCategory" placeholder="分类" clearable size="small" style="width: 120px" @change="loadPuzzles">
        <el-option label="残局" value="endgame" />
        <el-option label="将杀" value="mate" />
        <el-option label="战术" value="tactics" />
        <el-option label="开局" value="opening" />
        <el-option label="中局" value="middlegame" />
      </el-select>
      <el-select v-model="filterDifficulty" placeholder="难度" clearable size="small" style="width: 120px" @change="loadPuzzles">
        <el-option label="入门" value="beginner" />
        <el-option label="初级" value="easy" />
        <el-option label="中级" value="medium" />
        <el-option label="高级" value="hard" />
        <el-option label="专家" value="expert" />
      </el-select>
      <el-select v-model="filterSource" placeholder="来源" clearable size="small" style="width: 140px" @change="loadPuzzles">
        <el-option label="全部" value="" />
        <el-option label="系统预设" value="preset" />
        <el-option label="棋谱截取" value="user" />
        <el-option v-if="isLoggedIn" label="我创建的" value="mine" />
      </el-select>
      <el-button v-if="isLoggedIn" size="small" type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>创建残局
      </el-button>
    </div>

    <div v-if="loading" class="pl-loading">
      <el-skeleton :rows="5" animated />
    </div>

    <div v-else-if="puzzles.length === 0" class="pl-empty">
      <el-empty description="暂无残局数据">
        <template #description>
          <p>暂无残局数据</p>
          <p style="font-size: 12px; color: var(--text-color-secondary); margin-top: 4px;">前往棋谱库，在对局详细页截取残局</p>
        </template>
        <el-button type="primary" size="small" @click="$router.push('/games')">浏览棋谱库</el-button>
      </el-empty>
    </div>

    <div v-else class="pl-grid">
      <div v-for="p in puzzles" :key="p.id" class="pl-card" @click="selectPuzzle(p)">
        <div class="pl-card-header">
          <span class="pl-card-name">
            <span class="pl-card-num">#{{ String(p.puzzle_number || p.id).padStart(3, '0') }}</span>
            {{ p.name }}
          </span>
          <el-tag v-if="p.is_preset" type="info" size="small">预设</el-tag>
          <el-tag v-else type="success" size="small">棋谱截取</el-tag>
          <el-tag :type="diffTagType(p.difficulty)" size="small">{{ difficultyLabel(p.difficulty) }}</el-tag>
        </div>
        <div class="pl-card-body">
          <span class="pl-card-cat">{{ categoryLabel(p.category) }}</span>
          <span v-if="p.description" class="pl-card-desc">{{ p.description }}</span>
        </div>
        <div class="pl-card-footer">
          <div class="pl-card-stats">
            <span>练习 {{ p.practice_count || 0 }} 次</span>
            <span>解决 {{ p.solve_count || 0 }} 次</span>
          </div>
          <div v-if="p.source_game" class="pl-card-source">
            <router-link :to="`/games/${p.source_game.id}`" class="pl-source-link" @click.stop>
              来源: {{ p.source_game.white_player_name }} vs {{ p.source_game.black_player_name }}
            </router-link>
          </div>
        </div>
      </div>
    </div>

    <div v-if="total > perPage" class="pl-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="perPage"
        :total="total"
        layout="prev, pager, next"
        small
        @current-change="loadPuzzles"
      />
    </div>

    <el-dialog v-model="showDetailDialog" :title="selectedPuzzle?.name || '残局详情'" width="680px">
      <div v-if="selectedPuzzle" class="pl-detail">
        <div class="pl-detail-board">
          <PracticeBoard
            :fen="selectedPuzzle.fen"
            :user-color="'white'"
            :is-user-turn="false"
            :board-size="300"
          />
        </div>
        <div class="pl-detail-info">
          <div class="pl-detail-row">
            <span class="pl-detail-label">分类</span>
            <span>{{ categoryLabel(selectedPuzzle.category) }}</span>
          </div>
          <div class="pl-detail-row">
            <span class="pl-detail-label">难度</span>
            <el-tag :type="diffTagType(selectedPuzzle.difficulty)" size="small">{{ difficultyLabel(selectedPuzzle.difficulty) }}</el-tag>
          </div>
          <div class="pl-detail-row">
            <span class="pl-detail-label">练习次数</span>
            <span>{{ selectedPuzzle.practice_count || 0 }}</span>
          </div>
          <div class="pl-detail-row">
            <span class="pl-detail-label">解决次数</span>
            <span>{{ selectedPuzzle.solve_count || 0 }}</span>
          </div>
          <div v-if="selectedPuzzle.description" class="pl-detail-desc">
            {{ selectedPuzzle.description }}
          </div>
          <div v-if="selectedPuzzle.hint" class="pl-detail-hint">
            <el-icon><QuestionFilled /></el-icon>
            {{ selectedPuzzle.hint }}
          </div>
          <div v-if="selectedPuzzle.source_game" class="pl-detail-source">
            <span class="pl-detail-label">来源对局</span>
            <router-link :to="`/games/${selectedPuzzle.source_game.id}`" class="pl-source-link">
              {{ selectedPuzzle.source_game.white_player_name }} vs {{ selectedPuzzle.source_game.black_player_name }}
              <span v-if="selectedPuzzle.from_move">（第{{ selectedPuzzle.from_move }}步）</span>
            </router-link>
          </div>
          <div v-if="!selectedPuzzle.is_preset && !selectedPuzzle.source_game" class="pl-detail-source">
            <span class="pl-detail-label">来源</span>
            <span>自定义创建</span>
          </div>
        </div>
      </div>

      <div v-if="detailRecords.length > 0" class="pl-detail-records">
        <h4>练习记录</h4>
        <el-table :data="detailRecords" size="small" max-height="200">
          <el-table-column label="日期" width="140">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="难度" width="80">
            <template #default="{ row }">
              {{ difficultyLabel(row.difficulty) }}
            </template>
          </el-table-column>
          <el-table-column label="执棋" width="70">
            <template #default="{ row }">
              {{ row.user_color === 'w' ? '白方' : '黑方' }}
            </template>
          </el-table-column>
          <el-table-column label="结果" width="60">
            <template #default="{ row }">
              <span :class="recordResultClass(row)">{{ recordResultLabel(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="步数" prop="total_moves" width="60" />
          <el-table-column label="操作" width="70">
            <template #default="{ row }">
              <el-button size="small" type="primary" text @click="goReview(row)">复盘</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
        <el-button type="primary" @click="startPractice">开始练习</el-button>
      </template>
    </el-dialog>

    <!-- 创建残局对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建自定义残局" width="520px">
      <el-form :model="newPuzzle" label-width="80px" size="default">
        <el-form-item label="名称" required>
          <el-input v-model="newPuzzle.name" placeholder="例如：基础杀王练习" />
        </el-form-item>
        <el-form-item label="FEN" required>
          <el-input v-model="newPuzzle.fen" type="textarea" :rows="2" placeholder="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="newPuzzle.category" style="width: 100%">
            <el-option label="残局" value="endgame" />
            <el-option label="将杀" value="mate" />
            <el-option label="战术" value="tactics" />
            <el-option label="开局" value="opening" />
            <el-option label="中局" value="middlegame" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-select v-model="newPuzzle.difficulty" style="width: 100%">
            <el-option label="入门" value="beginner" />
            <el-option label="初级" value="easy" />
            <el-option label="中级" value="medium" />
            <el-option label="高级" value="hard" />
            <el-option label="专家" value="expert" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newPuzzle.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="提示">
          <el-input v-model="newPuzzle.hint" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { InfoFilled, QuestionFilled, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getPuzzles, getPuzzle, createPuzzle } from '@/api/practice'
import { useUserStore } from '@/store/userStore'
import PracticeBoard from '@/components/PracticeBoard.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const isLoggedIn = computed(() => userStore.isLoggedIn)
const currentUserId = ref(null)

const puzzles = ref([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const perPage = ref(20)

const filterCategory = ref('')
const filterDifficulty = ref('')
const filterSource = ref('')
const filterSourceGameId = ref(null)

const showCreateDialog = ref(false)
const newPuzzle = ref({ name: '', fen: '', category: 'endgame', difficulty: 'medium', description: '', hint: '' })
const creating = ref(false)

const showDetailDialog = ref(false)
const selectedPuzzle = ref(null)
const detailRecords = ref([])

function difficultyLabel(diff) {
  const map = { beginner: '入门', easy: '初级', medium: '中级', hard: '高级', expert: '专家' }
  return map[diff] || diff
}

function diffTagType(diff) {
  const map = { beginner: 'success', easy: '', medium: 'warning', hard: 'danger', expert: 'info' }
  return map[diff] || 'info'
}

function categoryLabel(cat) {
  const map = { endgame: '残局', mate: '将杀', tactics: '战术', opening: '开局', middlegame: '中局' }
  return map[cat] || cat
}

function formatDate(isoStr) {
  if (!isoStr) return '-'
  try {
    return new Date(isoStr).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return isoStr
  }
}

function recordResultLabel(row) {
  if (row.result === '1/2-1/2') return '和'
  if (row.result === '1-0' && row.user_color === 'w') return '胜'
  if (row.result === '0-1' && row.user_color === 'b') return '胜'
  return '负'
}

function recordResultClass(row) {
  if (row.result === '1/2-1/2') return 'pl-record-draw'
  if (row.result === '1-0' && row.user_color === 'w') return 'pl-record-win'
  if (row.result === '0-1' && row.user_color === 'b') return 'pl-record-win'
  return 'pl-record-lose'
}

async function loadPuzzles() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      per_page: perPage.value,
    }
    if (filterCategory.value) params.category = filterCategory.value
    if (filterDifficulty.value) params.difficulty = filterDifficulty.value
    if (filterSourceGameId.value) params.source_game_id = filterSourceGameId.value
    if (filterSource.value === 'mine' && isLoggedIn.value) {
      params.only_mine = 1
    }

    const res = await getPuzzles(params)
    const data = res.data || res
    let items = data.puzzles || []
    currentUserId.value = data.current_user_id || null

    if (filterSource.value === 'preset') {
      items = items.filter(p => p.is_preset)
    } else if (filterSource.value === 'user') {
      items = items.filter(p => !p.is_preset)
    }
    // 'mine' 已在后端过滤（only_mine=1）

    puzzles.value = items
    total.value = data.total || items.length
  } catch {
    puzzles.value = []
  } finally {
    loading.value = false
  }
}

async function submitCreate() {
  if (!newPuzzle.value.name || !newPuzzle.value.fen) {
    ElMessage.warning('请填写名称和 FEN')
    return
  }
  creating.value = true
  try {
    await createPuzzle(newPuzzle.value)
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    newPuzzle.value = { name: '', fen: '', category: 'endgame', difficulty: 'medium', description: '', hint: '' }
    await loadPuzzles()
  } catch (e) {
    ElMessage.error('创建失败: ' + (e.message || ''))
  } finally {
    creating.value = false
  }
}

async function selectPuzzle(p) {
  selectedPuzzle.value = p
  detailRecords.value = []
  showDetailDialog.value = true
  try {
    const res = await getPuzzle(p.id)
    const data = res.data || res
    selectedPuzzle.value = data
    detailRecords.value = data.practice_records || []
  } catch {
  }
}

function startPractice() {
  if (!selectedPuzzle.value) return
  showDetailDialog.value = false
  router.push({
    path: '/practice',
    query: { mode: 'puzzle', puzzle_id: selectedPuzzle.value.id },
  })
}

function goReview(row) {
  showDetailDialog.value = false
  router.push(`/practice/review/${row.id}`)
}

function clearSourceFilter() {
  filterSourceGameId.value = null
  router.replace({ path: '/puzzles' })
  loadPuzzles()
}

onMounted(() => {
  if (route.query.source_game_id) {
    filterSourceGameId.value = parseInt(route.query.source_game_id)
  }
  loadPuzzles()
})
</script>

<style scoped>
.puzzle-library-page {
  max-width: 1100px;
  margin: 0 auto;
}

.pl-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.pl-header h2 {
  margin: 0;
  font-size: 20px;
  color: var(--text-color);
}

.pl-header-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.pl-filter-hint {
  font-size: 13px;
  color: #409eff;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--hover-bg);
  padding: 4px 10px;
  border-radius: 4px;
}

.pl-header-hint {
  font-size: 12px;
  color: var(--text-color-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.pl-filters {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.pl-loading,
.pl-empty {
  padding: 40px 0;
}

.pl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

.pl-card {
  background: var(--card-bg);
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.pl-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.12);
}

.pl-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.pl-card-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-color);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pl-card-num {
  color: #409eff;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  margin-right: 4px;
}

.pl-card-body {
  margin-bottom: 8px;
}

.pl-card-cat {
  font-size: 12px;
  color: var(--text-color-secondary);
  margin-right: 8px;
}

.pl-card-desc {
  font-size: 12px;
  color: var(--text-color-regular);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.pl-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-color-secondary);
}

.pl-card-stats {
  display: flex;
  gap: 12px;
}

.pl-source-link {
  color: #409eff;
  text-decoration: none;
  font-size: 12px;
}

.pl-source-link:hover {
  text-decoration: underline;
}

.pl-pagination {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.pl-detail {
  display: flex;
  gap: 20px;
}

.pl-detail-board {
  flex-shrink: 0;
}

.pl-detail-info {
  flex: 1;
}

.pl-detail-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}

.pl-detail-label {
  color: var(--text-color-secondary);
  min-width: 60px;
}

.pl-detail-desc {
  font-size: 13px;
  color: var(--text-color-regular);
  line-height: 1.6;
  margin: 8px 0;
}

.pl-detail-hint {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  color: #e6a23c;
  font-size: 12px;
  margin-bottom: 8px;
}

.pl-detail-source {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}

.pl-detail-source a {
  color: #409eff;
  text-decoration: none;
}

.pl-detail-source a:hover {
  text-decoration: underline;
}

.pl-detail-records {
  margin-top: 16px;
  border-top: 1px solid var(--border-color-lighter);
  padding-top: 12px;
}

.pl-detail-records h4 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-color);
  margin: 0 0 8px 0;
}

.pl-record-win { color: #67c23a; font-weight: 600; }
.pl-record-lose { color: #f56c6c; font-weight: 600; }
.pl-record-draw { color: #e6a23c; font-weight: 600; }
</style>
