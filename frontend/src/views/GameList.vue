<template>
  <div class="game-list-page">
    <div class="gl-header">
      <h1>棋谱库</h1>
      <div class="gl-header-actions">
        <el-button type="primary" @click="goUpload">上传棋谱</el-button>
        <el-button :icon="Refresh" @click="fetchGames" :loading="loading">刷新</el-button>
      </div>
    </div>

    <div class="gl-filters">
      <el-input
        v-model="filters.player"
        placeholder="棋手搜索"
        clearable
        :prefix-icon="Search"
        style="width: 180px"
        @clear="onFilterChange"
        @keyup.enter="onFilterChange"
      />
      <el-select
        v-model="filters.eco"
        placeholder="ECO开局"
        clearable
        style="width: 150px"
        @change="onFilterChange"
      >
        <el-option v-for="eco in ecoOptions" :key="eco" :label="eco" :value="eco" />
      </el-select>
      <el-select
        v-model="filters.result"
        placeholder="结果"
        clearable
        style="width: 120px"
        @change="onFilterChange"
      >
        <el-option v-for="r in resultOptions.length ? resultOptions : ['1-0', '0-1', '1/2-1/2', '*']" :key="r" :label="r === '1-0' ? '白胜 1-0' : r === '0-1' ? '黑胜 0-1' : r === '1/2-1/2' ? '和棋 ½-½' : r" :value="r" />
      </el-select>
      <el-date-picker
        v-model="filters.dateRange"
        type="daterange"
        range-separator="-"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        style="width: 260px"
        @change="onFilterChange"
      />
      <el-select
        v-model="filters.sort"
        placeholder="排序"
        style="width: 130px"
        @change="onFilterChange"
      >
        <el-option label="最近添加" value="created_at" />
        <el-option label="对局日期" value="date" />
        <el-option label="白方等级分" value="white_elo" />
        <el-option label="黑方等级分" value="black_elo" />
        <el-option label="总步数" value="total_moves" />
        <el-option label="ECO代码" value="eco_code" />
      </el-select>
      <el-select
        v-model="filters.order"
        style="width: 90px"
        @change="onFilterChange"
      >
        <el-option label="降序" value="desc" />
        <el-option label="升序" value="asc" />
      </el-select>
      <el-button-group>
        <el-button :type="viewMode === 'card' ? 'primary' : ''" @click="viewMode = 'card'">
          <el-icon><Grid /></el-icon>
        </el-button>
        <el-button :type="viewMode === 'table' ? 'primary' : ''" @click="viewMode = 'table'">
          <el-icon><List /></el-icon>
        </el-button>
      </el-button-group>
      <el-button @click="clearFilters">清除筛选</el-button>
    </div>

    <div v-loading="loading" class="gl-content">
      <div v-if="!loading && games.length === 0" class="gl-empty">
        <el-empty description="暂无棋谱数据">
          <el-button type="primary" @click="goUpload">上传棋谱</el-button>
        </el-empty>
      </div>

      <template v-if="viewMode === 'card'">
        <el-row :gutter="16">
          <el-col
            v-for="game in games"
            :key="game.id"
            :xs="24"
            :sm="12"
            :md="8"
            :lg="6"
          >
            <el-card
              class="gl-card"
              shadow="hover"
              @click="goDetail(game.id)"
            >
              <div class="gl-card-preview">
                <canvas
                  :ref="el => setCanvasRef(game.id, el)"
                  class="gl-card-canvas"
                  width="160"
                  height="160"
                  :data-game-id="game.id"
                />
              </div>
              <div class="gl-card-info">
                <div class="gl-card-id-row">
                  <span class="gl-card-id">#{{ String(game.game_number || game.id).padStart(3, '0') }}</span>
                  <el-tag
                    :type="resultTagType(game.result)"
                    size="small"
                  >{{ game.result || '*' }}</el-tag>
                </div>
                <div class="gl-card-players">
                  <span class="gl-card-white">
                    {{ game.white_player_name || '未知' }}
                    <span v-if="game.white_elo" class="gl-card-elo">{{ game.white_elo }}</span>
                  </span>
                  <span class="gl-card-vs">vs</span>
                  <span class="gl-card-black">
                    {{ game.black_player_name || '未知' }}
                    <span v-if="game.black_elo" class="gl-card-elo">{{ game.black_elo }}</span>
                  </span>
                </div>
                <div class="gl-card-meta">
                  <span v-if="game.eco_code" class="gl-card-eco">{{ game.eco_code }}</span>
                </div>
                <div class="gl-card-date">{{ formatDate(game.date) }}</div>
                <div v-if="game.tournament_name" class="gl-card-event">{{ game.tournament_name }}</div>
              </div>
              <div v-if="isAdmin" class="gl-card-actions" @click.stop>
                <el-checkbox v-model="game._selected" @change="onSelectGame(game)" />
                <el-button
                  type="danger"
                  size="small"
                  text
                  @click.stop="onDeleteGame(game)"
                >删除</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </template>

      <template v-else>
        <el-table ref="gameTableRef" :data="games" stripe style="width: 100%" @row-click="(row) => goDetail(row.id)" class="gl-table">
          <el-table-column prop="id" label="#" width="70" sortable>
            <template #default="{ row }">{{ row.game_number || row.id }}</template>
          </el-table-column>
          <el-table-column label="白方" min-width="140">
            <template #default="{ row }">
              <span class="gl-tbl-player">{{ row.white_player_name || '未知' }}</span>
              <span v-if="row.white_elo" class="gl-tbl-elo">({{ row.white_elo }})</span>
            </template>
          </el-table-column>
          <el-table-column label="黑方" min-width="140">
            <template #default="{ row }">
              <span class="gl-tbl-player">{{ row.black_player_name || '未知' }}</span>
              <span v-if="row.black_elo" class="gl-tbl-elo">({{ row.black_elo }})</span>
            </template>
          </el-table-column>
          <el-table-column prop="result" label="结果" width="80">
            <template #default="{ row }">
              <el-tag :type="resultTagType(row.result)" size="small">{{ row.result || '*' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="eco_code" label="ECO" width="80" sortable>
            <template #default="{ row }">{{ row.eco_code || '-' }}</template>
          </el-table-column>
          <el-table-column prop="total_moves" label="步数" width="70" sortable>
            <template #default="{ row }">{{ row.total_moves || '-' }}</template>
          </el-table-column>
          <el-table-column prop="date" label="日期" width="110" sortable>
            <template #default="{ row }">{{ formatDate(row.date) }}</template>
          </el-table-column>
          <el-table-column prop="tournament_name" label="赛事" min-width="120">
            <template #default="{ row }">{{ row.tournament_name || '-' }}</template>
          </el-table-column>
        </el-table>
      </template>
    </div>

    <div v-if="games.length" class="gl-pagination">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[12, 24, 36, 48]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="onPageSizeChange"
        @current-change="onPageChange"
      />
    </div>

    <div v-if="isAdmin && selectedGames.length" class="gl-batch-bar">
      <span>已选择 {{ selectedGames.length }} 局</span>
      <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      <el-button size="small" @click="clearSelection">取消选择</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Grid, List } from '@element-plus/icons-vue'
import { getGames, deleteGame, getGameFilters } from '@/api/games'

const router = useRouter()

const loading = ref(false)
const games = ref([])
const canvasRefs = {}
const ecoOptions = ref([])
const resultOptions = ref([])
const viewMode = ref('card')

const isAdmin = computed(() => {
  return !!localStorage.getItem('token')
})

const selectedGames = computed(() => games.value.filter(g => g._selected))

const gameTableRef = ref(null)

const filters = reactive({
  player: '',
  eco: '',
  result: '',
  dateRange: null,
  sort: 'created_at',
  order: 'desc',
})

const pagination = reactive({
  page: 1,
  pageSize: 12,
  total: 0,
})

async function fetchFilterOptions() {
  try {
    const res = await getGameFilters()
    const data = res.data || res
    ecoOptions.value = data.eco_codes || []
    resultOptions.value = data.results || []
  } catch { /* ignore */ }
}

function setCanvasRef(id, el) {
  if (el) canvasRefs[id] = el
}

function resultTagType(result) {
  if (result === '1-0') return 'success'
  if (result === '0-1') return 'danger'
  if (result === '1/2-1/2') return 'warning'
  return 'info'
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  if (dateStr.length === 4) return dateStr
  if (dateStr.length === 7) return dateStr.replace('.', '-')
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('zh-CN')
  } catch {
    return dateStr
  }
}

async function fetchGames() {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      per_page: pagination.pageSize,
    }
    if (filters.player) params.player = filters.player
    if (filters.eco) params.eco = filters.eco
    if (filters.result) params.result = filters.result
    if (filters.dateRange && filters.dateRange.length === 2) {
      params.date_from = filters.dateRange[0]
      params.date_to = filters.dateRange[1]
    }
    params.sort = filters.sort
    params.order = filters.order

    const res = await getGames(params)
    const data = res.data || res
    games.value = (data.items || data.games || []).map(g => ({ ...g, _selected: false }))
    pagination.total = data.total || games.value.length

    await nextTick()
    observeCanvases()
  } catch (e) {
    ElMessage.error('加载棋谱失败：' + e.message)
  } finally {
    loading.value = false
  }
}

let canvasObserver = null
const drawnCanvases = new Set()

function observeCanvases() {
  if (canvasObserver) canvasObserver.disconnect()
  drawnCanvases.clear()
  canvasObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const canvas = entry.target
        const gameId = canvas.dataset.gameId
        if (gameId && !drawnCanvases.has(gameId)) {
          drawnCanvases.add(gameId)
          const game = games.value.find(g => g.id === parseInt(gameId))
          if (game) drawMiniBoard(game)
          canvasObserver.unobserve(canvas)
        }
      }
    })
  }, { rootMargin: '200px' })

  Object.values(canvasRefs).forEach(canvas => {
    if (canvas && !drawnCanvases.has(canvas.dataset.gameId)) {
      canvasObserver.observe(canvas)
    }
  })
}

function drawMiniBoard(game) {
  const canvas = canvasRefs[game.id]
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const size = 160
  const sq = size / 8

  const lightColor = '#f0d9b5'
  const darkColor = '#b58863'

  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      ctx.fillStyle = (r + c) % 2 === 0 ? lightColor : darkColor
      ctx.fillRect(c * sq, r * sq, sq, sq)
    }
  }

  const fen = game.final_fen || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR'
  const pieceMap = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟',
  }
  const rows = fen.split(' ')[0].split('/')
  for (let r = 0; r < rows.length; r++) {
    let c = 0
    for (const ch of rows[r]) {
      if (ch >= '1' && ch <= '8') {
        c += parseInt(ch)
      } else if (pieceMap[ch]) {
        ctx.font = `${sq * 0.75}px serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillStyle = ch === ch.toUpperCase() ? '#fff' : '#000'
        ctx.strokeStyle = ch === ch.toUpperCase() ? '#000' : '#fff'
        ctx.lineWidth = 0.5
        const x = c * sq + sq / 2
        const y = r * sq + sq / 2
        ctx.strokeText(pieceMap[ch], x, y)
        ctx.fillText(pieceMap[ch], x, y)
        c++
      }
    }
  }
}

function onFilterChange() {
  pagination.page = 1
  gameTableRef.value?.clearSort()
  fetchGames()
}

function clearFilters() {
  filters.player = ''
  filters.eco = ''
  filters.result = ''
  filters.dateRange = null
  filters.sort = 'created_at'
  filters.order = 'desc'
  onFilterChange()
}

function onPageChange() {
  fetchGames()
}

function onPageSizeChange() {
  pagination.page = 1
  fetchGames()
}

function goDetail(id) {
  router.push({ name: 'GameDetail', params: { id } })
}

function goUpload() {
  router.push({ name: 'Upload' })
}

function onSelectGame(game) {
  // checkbox toggle handled by v-model
}

function clearSelection() {
  games.value.forEach(g => { g._selected = false })
}

async function onDeleteGame(game) {
  try {
    await ElMessageBox.confirm(
      `确定删除 ${game.white_player_name || '?'} vs ${game.black_player_name || '?'} 的对局？`,
      '确认删除',
      { type: 'warning' }
    )
  } catch { return }
  try {
    await deleteGame(game.id)
    ElMessage.success('删除成功')
    fetchGames()
  } catch (err) {
    const resp = err.response
    if (resp && resp.status === 409) {
      const related = resp.data?.related || {}
      const msg = `该棋谱存在关联数据（收藏 ${related.collections || 0}、浏览 ${related.browsing_history || 0}、残局 ${related.puzzles || 0}），是否强制删除？`
      try {
        await ElMessageBox.confirm(msg, '存在关联数据', { type: 'warning', confirmButtonText: '强制删除', cancelButtonText: '取消' })
      } catch { return }
      try {
        await deleteGame(game.id, true)
        ElMessage.success('删除成功')
        fetchGames()
      } catch (e2) {
        ElMessage.error('删除失败: ' + ((e2.response?.data?.error) || e2.message || ''))
      }
    } else {
      ElMessage.error('删除失败: ' + ((resp?.data?.error) || err.message || ''))
    }
  }
}

async function batchDelete() {
  const ids = selectedGames.value.map(g => g.id)
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${ids.length} 局对局？`,
      '批量删除',
      { type: 'warning' }
    )
  } catch { return }
  try {
    for (const id of ids) {
      await deleteGame(id, true)
    }
    ElMessage.success('批量删除成功')
    fetchGames()
  } catch (err) {
    ElMessage.error('批量删除失败: ' + ((err.response?.data?.error) || err.message || ''))
  }
}

onMounted(() => {
  fetchFilterOptions()
  const saved = sessionStorage.getItem('gameListState')
  if (saved) {
    try {
      const state = JSON.parse(saved)
      if (state.page) pagination.page = state.page
      if (state.pageSize) pagination.pageSize = state.pageSize
      if (state.filters) Object.assign(filters, state.filters)
    } catch { /* ignore */ }
  }
  const query = route.query
  if (query.player) filters.player = query.player
  fetchGames()
})

const route = useRoute()

onBeforeUnmount(() => {
  sessionStorage.setItem('gameListState', JSON.stringify({
    page: pagination.page,
    pageSize: pagination.pageSize,
    filters: { player: filters.player, eco: filters.eco, result: filters.result },
  }))
})
</script>

<style scoped>
.game-list-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.gl-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.gl-header h1 {
  margin: 0;
  color: var(--text-color);
}

.gl-header-actions {
  display: flex;
  gap: 8px;
}

.gl-filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 20px;
  padding: 16px;
  background: var(--card-bg);
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.gl-content {
  min-height: 300px;
}

.gl-empty {
  padding: 60px 0;
}

.gl-card {
  margin-bottom: 16px;
  cursor: pointer;
  transition: transform 0.2s;
}

.gl-card:hover {
  transform: translateY(-4px);
}

:deep(.gl-card .el-card__body) {
  padding: 0;
}

.gl-card-preview {
  width: 100%;
  aspect-ratio: 1;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.gl-card-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.gl-card-info {
  padding: 10px 12px;
}

.gl-card-id-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.gl-card-id {
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
}

.gl-card-players {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gl-card-vs {
  color: var(--text-color-secondary);
  font-weight: 400;
  margin: 0 4px;
}

.gl-card-elo {
  color: var(--text-color-secondary);
  font-weight: 400;
  font-size: 12px;
  margin-left: 2px;
}

.gl-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.gl-card-result {
  font-size: 12px;
}

.gl-card-eco {
  font-size: 12px;
  color: var(--text-color-secondary);
  background: #f4f4f5;
  padding: 1px 6px;
  border-radius: 3px;
}

.gl-card-date {
  font-size: 12px;
  color: var(--text-color-secondary);
}

.gl-card-event {
  font-size: 12px;
  color: var(--text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

.gl-card-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  border-top: 1px solid #f0f0f0;
}

.gl-pagination {
  display: flex;
  justify-content: center;
  margin-top: 24px;
  padding: 16px 0;
}

.gl-batch-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--card-bg);
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
  padding: 10px 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 100;
}

.gl-table {
  cursor: pointer;
}

.gl-tbl-player {
  font-weight: 600;
  color: var(--text-color);
}

.gl-tbl-elo {
  color: var(--text-color-secondary);
  font-size: 12px;
  margin-left: 2px;
}
</style>
