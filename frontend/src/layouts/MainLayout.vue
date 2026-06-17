<template>
  <el-container class="main-layout">
    <el-header class="ml-header" height="60px">
      <div class="ml-header-left">
        <div class="ml-logo" @click="router.push('/')">
          <span class="ml-logo-icon">♚</span>
          <span class="ml-logo-text">ChessDB</span>
        </div>
        <el-menu
          :default-active="activeMenu"
          mode="horizontal"
          :ellipsis="false"
          class="ml-nav"
          @select="onNavSelect"
        >
          <el-menu-item index="/games">棋谱库</el-menu-item>
          <el-menu-item index="/players">棋手</el-menu-item>
          <el-menu-item index="/openings">开局库</el-menu-item>
          <el-menu-item index="/puzzles">残局库</el-menu-item>
          <el-menu-item index="/practice">AI对弈</el-menu-item>
          <el-menu-item index="/stats">数据分析</el-menu-item>
          <el-menu-item index="/upload">上传</el-menu-item>
        </el-menu>
      </div>

      <div class="ml-header-right">
        <el-input
          v-model="searchQuery"
          placeholder="搜索棋谱或棋手..."
          :prefix-icon="Search"
          clearable
          size="default"
          class="ml-search"
          @keyup.enter="onSearch"
        />

        <ThemeSwitch />

        <template v-if="userStore.isLoggedIn">
          <el-dropdown trigger="click" @command="onUserCommand">
            <div class="ml-user-avatar">
              <el-avatar :size="32" :icon="UserFilled" />
              <span class="ml-user-name">{{ userStore.user?.username || '用户' }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人设置</el-dropdown-item>
                <el-dropdown-item command="analysis">分析队列</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template v-else>
          <el-button size="default" @click="router.push('/login')">登录</el-button>
          <el-button size="default" type="primary" @click="router.push('/register')">注册</el-button>
        </template>

        <el-button
          class="ml-sidebar-toggle"
          :icon="Fold"
          text
          @click="uiStore.toggleSidebar"
        />
      </div>
    </el-header>

    <el-container class="ml-body">
      <el-aside
        v-if="showSidebar"
        :width="uiStore.sidebarCollapsed ? '0px' : '200px'"
        class="ml-sidebar"
      >
        <div v-show="!uiStore.sidebarCollapsed" class="ml-sidebar-content">
          <div class="ml-sidebar-section">
            <div class="ml-sidebar-title">快速导航</div>
            <div class="ml-sidebar-links">
              <div class="ml-sidebar-link" @click="router.push('/')">
                <el-icon><HomeFilled /></el-icon> 首页
              </div>
              <div class="ml-sidebar-link" @click="router.push('/games')">
                <el-icon><Document /></el-icon> 棋谱库
              </div>
              <div class="ml-sidebar-link" @click="router.push('/players')">
                <el-icon><User /></el-icon> 棋手
              </div>
              <div class="ml-sidebar-link" @click="router.push('/openings')">
                <el-icon><Reading /></el-icon> 开局库
              </div>
              <div class="ml-sidebar-link" @click="router.push('/puzzles')">
                <el-icon><Reading /></el-icon> 残局库
              </div>
              <div class="ml-sidebar-group">
                <div class="ml-sidebar-link" @click="togglePracticeSubmenu">
                  <el-icon><Trophy /></el-icon> AI对弈练习
                  <el-icon class="ml-sidebar-arrow" :class="{ 'is-open': practiceSubmenuOpen }"><ArrowRight /></el-icon>
                </div>
                <div v-show="practiceSubmenuOpen" class="ml-sidebar-sub">
                  <div class="ml-sidebar-link" @click="router.push('/practice')">
                    开始练习
                  </div>
                  <div class="ml-sidebar-link" @click="router.push('/practice/history')">
                    练习历史
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="ml-sidebar-section">
            <div class="ml-sidebar-title-row">
              <span class="ml-sidebar-title">最近浏览</span>
              <router-link to="/browsing" class="ml-sidebar-more">查看全部</router-link>
            </div>
            <div v-if="recentGames.length === 0" class="ml-sidebar-empty">暂无记录</div>
            <div
              v-for="g in recentGames"
              :key="g.id"
              class="ml-sidebar-link"
              @click="router.push(`/games/${g.id}`)"
            >
              <el-icon><Document /></el-icon>
              {{ g.white }} vs {{ g.black }}
            </div>
          </div>

          <div v-if="userStore.isLoggedIn" class="ml-sidebar-section">
            <div class="ml-sidebar-title-row">
              <span class="ml-sidebar-title">我的收藏</span>
              <router-link to="/favorites" class="ml-sidebar-more">查看全部</router-link>
            </div>
            <div v-if="favoriteGames.length === 0" class="ml-sidebar-empty">暂无收藏</div>
            <div
              v-for="g in favoriteGames"
              :key="g.id"
              class="ml-sidebar-link"
              @click="router.push(`/games/${g.game_id}`)"
            >
              <el-icon><Star /></el-icon>
              {{ g.white_player_name || '?' }} vs {{ g.black_player_name || '?' }}
            </div>
          </div>

          <div v-if="userStore.isLoggedIn && userStore.isAdmin" class="ml-sidebar-section">
            <div class="ml-sidebar-title-row">
              <span class="ml-sidebar-title">管理员</span>
            </div>
            <div class="ml-sidebar-link ml-sidebar-link-admin" @click="router.push('/admin/center/overview')">
              <el-icon><Setting /></el-icon> 管理中心
            </div>
          </div>

          <div class="ml-sidebar-section ml-sidebar-bottom">
            <div class="ml-sidebar-link" @click="router.push('/help')">
              <el-icon><QuestionFilled /></el-icon> 帮助中心
            </div>
          </div>
        </div>
      </el-aside>

      <el-main class="ml-main">
        <div v-if="breadcrumbs.length > 1" class="ml-breadcrumb">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item
              v-for="(crumb, i) in breadcrumbs"
              :key="i"
              :to="i < breadcrumbs.length - 1 ? crumb.to : undefined"
            >{{ crumb.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <router-view v-slot="{ Component }">
          <transition name="ml-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>

    <el-footer height="40px" class="ml-footer">
      <span>&copy; 2024 ChessDB</span>
      <span class="ml-footer-sep">|</span>
      <a href="javascript:void(0)">关于</a>
      <span class="ml-footer-sep">|</span>
      <router-link to="/help">帮助</router-link>
    </el-footer>

    <el-drawer
      v-model="mobileDrawerVisible"
      direction="ltr"
      size="260px"
      :show-close="false"
      class="ml-mobile-drawer"
    >
      <template #header>
        <div class="ml-logo" @click="mobileDrawerVisible = false; router.push('/')">
          <span class="ml-logo-icon">♚</span>
          <span class="ml-logo-text">ChessDB</span>
        </div>
      </template>
      <el-menu :default-active="activeMenu" @select="onMobileNavSelect">
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon> 首页
        </el-menu-item>
        <el-menu-item index="/games">
          <el-icon><Document /></el-icon> 棋谱库
        </el-menu-item>
        <el-menu-item index="/players">
          <el-icon><User /></el-icon> 棋手
        </el-menu-item>
        <el-menu-item index="/openings">
          <el-icon><Reading /></el-icon> 开局库
        </el-menu-item>
        <el-menu-item index="/puzzles">
          <el-icon><Reading /></el-icon> 残局库
        </el-menu-item>
        <el-sub-menu index="/practice">
          <template #title>
            <el-icon><Trophy /></el-icon> AI对弈练习
          </template>
          <el-menu-item index="/practice">开始练习</el-menu-item>
          <el-menu-item index="/practice/history">练习历史</el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/upload">
          <el-icon><Upload /></el-icon> 上传棋谱
        </el-menu-item>
      </el-menu>
    </el-drawer>

    <el-dialog v-model="showWelcome" title="欢迎使用 ChessDB" width="480px" :close-on-click-modal="false" :show-close="true">
      <div class="ml-welcome">
        <p class="ml-welcome-desc">ChessDB 是一个国际象棋棋谱管理和AI对弈练习平台。以下是快速入门指南：</p>
        <div class="ml-welcome-steps">
          <div class="ml-welcome-step">
            <span class="ml-welcome-step-num">1</span>
            <span>浏览和搜索棋谱库中的对局</span>
          </div>
          <div class="ml-welcome-step">
            <span class="ml-welcome-step-num">2</span>
            <span>上传PGN文件录入新棋谱</span>
          </div>
          <div class="ml-welcome-step">
            <span class="ml-welcome-step-num">3</span>
            <span>与AI对弈练习，提升棋力</span>
          </div>
          <div class="ml-welcome-step">
            <span class="ml-welcome-step-num">4</span>
            <span>从棋谱截取残局，反复练习</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="dismissWelcome">稍后再看</el-button>
        <router-link to="/help" @click="dismissWelcome">
          <el-button type="primary">查看完整教程</el-button>
        </router-link>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Search,
  Fold,
  UserFilled,
  HomeFilled,
  Document,
  User,
  Reading,
  Star,
  Upload,
  Trophy,
  ArrowRight,
  QuestionFilled,
} from '@element-plus/icons-vue'
import { useUserStore, useUiStore } from '@/store'
import { getCollections } from '@/api/collections'
import { getBrowsingHistory } from '@/api/browsing'
import ThemeSwitch from '@/components/ThemeSwitch.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const uiStore = useUiStore()

const searchQuery = ref('')
const mobileDrawerVisible = ref(false)
const isMobile = ref(false)
const practiceSubmenuOpen = ref(true)
const showWelcome = ref(false)

function dismissWelcome() {
  showWelcome.value = false
  localStorage.setItem('chessdb_welcome_dismissed', '1')
}

const recentGames = ref([])
const favoriteGames = ref([])

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/games')) return '/games'
  if (path.startsWith('/players')) return '/players'
  if (path.startsWith('/openings')) return '/openings'
  if (path.startsWith('/puzzles')) return '/puzzles'
  if (path.startsWith('/practice')) return '/practice'
  if (path.startsWith('/upload')) return '/upload'
  return '/'
})

const showSidebar = computed(() => !isMobile.value)

const breadcrumbs = computed(() => {
  const crumbs = [{ title: '首页', to: '/' }]
  const path = route.path
  const title = route.meta.title

  if (path === '/') return crumbs

  if (path.startsWith('/games/')) {
    crumbs.push({ title: '棋谱库', to: '/games' })
    crumbs.push({ title: title || '对局详情' })
  } else if (path.startsWith('/players/')) {
    crumbs.push({ title: '棋手列表', to: '/players' })
    crumbs.push({ title: title || '棋手详情' })
  } else if (path.startsWith('/practice/review/')) {
    crumbs.push({ title: 'AI对弈练习', to: '/practice' })
    crumbs.push({ title: title || '练习复盘' })
  } else if (path.startsWith('/practice/history')) {
    crumbs.push({ title: 'AI对弈练习', to: '/practice' })
    crumbs.push({ title: title || '练习历史' })
  } else if (path.startsWith('/practice')) {
    crumbs.push({ title: title || 'AI对弈练习' })
  } else if (path.startsWith('/favorites')) {
    crumbs.push({ title: title || '我的收藏' })
  } else if (path.startsWith('/browsing')) {
    crumbs.push({ title: title || '最近浏览' })
  } else if (title) {
    crumbs.push({ title, to: path })
  }

  return crumbs
})

function onNavSelect(index) {
  router.push(index)
}

function togglePracticeSubmenu() {
  practiceSubmenuOpen.value = !practiceSubmenuOpen.value
}

function onMobileNavSelect(index) {
  mobileDrawerVisible.value = false
  router.push(index)
}

function onSearch() {
  if (!searchQuery.value.trim()) return
  router.push({ path: '/games', query: { player: searchQuery.value.trim() } })
}

function onUserCommand(command) {
  if (command === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/')
  } else if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'analysis') {
    router.push('/analysis')
  }
}

function checkMobile() {
  isMobile.value = window.innerWidth < 768
}

async function loadFavorites() {
  if (!userStore.isLoggedIn) {
    favoriteGames.value = []
    return
  }
  try {
    const res = await getCollections({ per_page: 5 })
    const data = res.data || res
    favoriteGames.value = data.items || []
  } catch {
    favoriteGames.value = []
  }
}

async function loadRecentGames() {
  if (!userStore.isLoggedIn) {
    const stored = localStorage.getItem('recentGames')
    if (stored) {
      try { recentGames.value = JSON.parse(stored) } catch { /* ignore */ }
    }
    return
  }
  try {
    const res = await getBrowsingHistory({ per_page: 5 })
    const data = res.data || res
    recentGames.value = (data.items || []).map(item => ({
      id: item.game_id,
      white: item.white_player_name || '?',
      black: item.black_player_name || '?',
    }))
  } catch {
    const stored = localStorage.getItem('recentGames')
    if (stored) {
      try { recentGames.value = JSON.parse(stored) } catch { /* ignore */ }
    }
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  loadRecentGames()
  loadFavorites()
  if (!localStorage.getItem('chessdb_welcome_dismissed')) {
    setTimeout(() => { showWelcome.value = true }, 800)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
.main-layout {
  min-height: 100vh;
  background: var(--bg-color-secondary);
}

.ml-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: var(--header-bg);
  border-bottom: 1px solid var(--border-color-light);
  box-shadow: var(--card-shadow);
  z-index: 100;
}

.ml-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ml-logo {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  margin-right: 12px;
  flex-shrink: 0;
}

.ml-logo-icon {
  font-size: 28px;
  color: #409eff;
}

.ml-logo-text {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-color);
  letter-spacing: 1px;
}

.ml-nav {
  border-bottom: none !important;
}

.ml-nav .el-menu-item {
  font-size: 14px;
}

.ml-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ml-search {
  width: 220px;
}

.ml-user-avatar {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.ml-user-avatar:hover {
  background: var(--hover-bg);
}

.ml-user-name {
  font-size: 14px;
  color: var(--text-color);
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ml-sidebar-toggle {
  display: none;
}

.ml-body {
  flex: 1;
  overflow: hidden;
}

.ml-sidebar {
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border-color-light);
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.3s;
}

.ml-sidebar-content {
  width: 200px;
  padding: 12px 0;
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.ml-sidebar-section {
  padding: 0 12px;
  margin-bottom: 16px;
}

.ml-sidebar-bottom {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--border-color-lighter);
}

.ml-sidebar-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
  padding-left: 4px;
}

.ml-sidebar-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding-left: 4px;
}

.ml-sidebar-title-row .ml-sidebar-title {
  margin-bottom: 0;
}

.ml-sidebar-more {
  font-size: 11px;
  color: #409eff;
  text-decoration: none;
}

.ml-sidebar-more:hover {
  text-decoration: underline;
}

.ml-sidebar-empty {
  font-size: 12px;
  color: var(--text-color-placeholder);
  padding: 4px;
}

.ml-sidebar-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  font-size: 13px;
  color: var(--text-color-regular);
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ml-sidebar-link:hover {
  background: var(--hover-bg);
  color: #409eff;
}

.ml-sidebar-group .ml-sidebar-link {
  width: 100%;
  box-sizing: border-box;
}

.ml-sidebar-arrow {
  margin-left: auto;
  transition: transform 0.2s;
  font-size: 12px;
  color: var(--text-color-secondary);
}

.ml-sidebar-arrow.is-open {
  transform: rotate(90deg);
}

.ml-sidebar-sub {
  padding-left: 20px;
}

.ml-sidebar-sub .ml-sidebar-link {
  font-size: 12px;
  padding: 4px 8px;
  color: var(--text-color-secondary);
}

.ml-sidebar-sub .ml-sidebar-link:hover {
  color: #409eff;
}

.ml-main {
  padding: 20px;
  overflow-y: auto;
  background: var(--bg-color-secondary);
}

.ml-breadcrumb {
  margin-bottom: 16px;
}

.ml-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--header-bg);
  border-top: 1px solid var(--border-color-light);
  font-size: 12px;
  color: var(--text-color-secondary);
}

.ml-footer a {
  color: var(--text-color-secondary);
  text-decoration: none;
}

.ml-footer a:hover {
  color: #409eff;
}

.ml-footer-sep {
  color: var(--border-color);
}

.ml-fade-enter-active,
.ml-fade-leave-active {
  transition: opacity 0.2s ease;
}

.ml-fade-enter-from,
.ml-fade-leave-to {
  opacity: 0;
}

@media (max-width: 992px) {
  .ml-search {
    width: 160px;
  }
  .ml-nav {
    display: none !important;
  }
  .ml-sidebar-toggle {
    display: inline-flex;
  }
}

@media (max-width: 768px) {
  .ml-header {
    padding: 0 12px;
  }
  .ml-search {
    width: 120px;
  }
  .ml-logo-text {
    display: none;
  }
  .ml-user-name {
    display: none;
  }
  .ml-main {
    padding: 12px;
  }
}

.ml-welcome {
  text-align: center;
}

.ml-welcome-desc {
  font-size: 14px;
  color: var(--text-color-regular);
  line-height: 1.6;
  margin: 0 0 20px 0;
}

.ml-welcome-steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
  text-align: left;
}

.ml-welcome-step {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--text-color);
}

.ml-welcome-step-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
</style>
