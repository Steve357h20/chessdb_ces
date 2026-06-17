<template>
  <div class="ao-root">
    <h3 class="ao-h">运营总览</h3>
    <el-row :gutter="16" class="ao-stat-row">
      <el-col :xs="12" :sm="6" v-for="c in statCards" :key="c.label">
        <div class="ao-stat-card" :style="{ borderLeft: `4px solid ${c.color}` }">
          <div class="ao-stat-label">{{ c.label }}</div>
          <div class="ao-stat-value">{{ c.value }}</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="ao-charts">
      <el-col :xs="24" :md="12">
        <div class="ao-chart-card">
          <h4>用户活跃度（24h 趋势）</h4>
          <div ref="activityChartRef" class="ao-chart"></div>
        </div>
      </el-col>
      <el-col :xs="24" :md="12">
        <div class="ao-chart-card">
          <h4>API 端点 × 时段 热力图（24h）</h4>
          <div ref="heatmapChartRef" class="ao-chart"></div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="ao-charts">
      <el-col :xs="24" :md="12">
        <div class="ao-chart-card">
          <h4>申请审核 - 状态分布</h4>
          <div ref="statusChartRef" class="ao-chart"></div>
        </div>
      </el-col>
      <el-col :xs="24" :md="12">
        <div class="ao-chart-card">
          <h4>申请审核 - 近 30 天堆叠趋势</h4>
          <div ref="auditTrendChartRef" class="ao-chart"></div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import {
  getAdminStats,
  getAnalyticsUserActivity,
  getAnalyticsHeatmap,
  getAnalyticsAuditStats,
} from '@/api/admin'

const stats = ref({})
const activity = ref({ series: { guest: [], user: [], admin: [] }, online_estimate: 0 })
const heatmap = ref({ x_axis: [], y_axis: [], matrix: [] })
const auditStats = ref({ by_status: [], by_day: [] })

const statCards = computed(() => [
  { label: '用户总数', value: stats.value.users ?? 0, color: '#409eff' },
  { label: '管理员', value: stats.value.admin_count ?? 0, color: '#f56c6c' },
  { label: '待审核', value: stats.value.pending_mod ?? 0, color: '#e6a23c' },
  { label: '已通过', value: stats.value.approved_mod ?? 0, color: '#67c23a' },
  { label: '已拒绝', value: stats.value.rejected_mod ?? 0, color: '#909399' },
  { label: 'API 调用(24h)', value: stats.value.api_calls_24h ?? 0, color: '#409eff' },
  { label: '错误数(24h)', value: stats.value.errors_24h ?? 0, color: '#f56c6c' },
  { label: '当前在线(token)', value: activity.value.online_estimate ?? 0, color: '#67c23a' },
])

const activityChartRef = ref(null)
const heatmapChartRef = ref(null)
const statusChartRef = ref(null)
const auditTrendChartRef = ref(null)
let activityIns = null, heatmapIns = null, statusIns = null, auditTrendIns = null

async function loadAll() {
  const [s, a, hm, au] = await Promise.all([
    getAdminStats().catch(() => ({})),
    getAnalyticsUserActivity({ hours: 24 }).catch(() => ({ series: { guest: [], user: [], admin: [] }, online_estimate: 0 })),
    getAnalyticsHeatmap({ hours: 24, top: 20 }).catch(() => ({ x_axis: [], y_axis: [], matrix: [] })),
    getAnalyticsAuditStats({ days: 30 }).catch(() => ({ by_status: [], by_day: [] })),
  ])
  stats.value = s.data || s
  activity.value = a.data || a
  heatmap.value = hm.data || hm
  auditStats.value = au.data || au
  await nextTick()
  renderCharts()
}

function renderCharts() {
  // 1) 用户活跃度 - 堆叠面积图
  if (activityChartRef.value) {
    activityIns = activityIns || echarts.init(activityChartRef.value)
    const guest = activity.value.series.guest || []
    const user = activity.value.series.user || []
    const admin = activity.value.series.admin || []
    const xAll = [...new Set([...guest.map(g => g.hour), ...user.map(g => g.hour), ...admin.map(g => g.hour)])].sort()
    const find = (arr, h) => (arr.find(a => a.hour === h)?.count ?? 0)
    activityIns.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['游客', '登录用户', '管理员'], top: 0 },
      grid: { left: 50, right: 20, top: 30, bottom: 30 },
      xAxis: { type: 'category', data: xAll.map(h => h.slice(11)) },
      yAxis: { type: 'value' },
      series: [
        { name: '游客', type: 'line', stack: 'act', smooth: true, areaStyle: {}, data: xAll.map(h => find(guest, h)), itemStyle: { color: '#909399' } },
        { name: '登录用户', type: 'line', stack: 'act', smooth: true, areaStyle: {}, data: xAll.map(h => find(user, h)), itemStyle: { color: '#409eff' } },
        { name: '管理员', type: 'line', stack: 'act', smooth: true, areaStyle: {}, data: xAll.map(h => find(admin, h)), itemStyle: { color: '#f56c6c' } },
      ],
    })
  }

  // 2) 端点 × 时段 热力图
  if (heatmapChartRef.value) {
    heatmapIns = heatmapIns || echarts.init(heatmapChartRef.value)
    const x = heatmap.value.x_axis.map(p => p.replace(/^\/api\//, ''))
    const y = heatmap.value.y_axis
    const max = Math.max(1, ...heatmap.value.matrix.map(c => c[2]))
    heatmapIns.setOption({
      tooltip: { position: 'top' },
      grid: { left: 100, right: 30, top: 10, bottom: 60 },
      xAxis: { type: 'category', data: x, axisLabel: { rotate: 45, fontSize: 9 }, splitArea: { show: true } },
      yAxis: { type: 'category', data: y.map(h => `${h}h`), splitArea: { show: true } },
      visualMap: {
        min: 0, max, calculable: true, orient: 'horizontal',
        left: 'center', bottom: 0, itemWidth: 12, itemHeight: 80,
        inRange: { color: ['#e0f3db', '#a8ddb5', '#7bccc4', '#4eb3d3', '#2b8cbe', '#08589e'] },
      },
      series: [{ name: '调用', type: 'heatmap', data: heatmap.value.matrix, emphasis: { itemStyle: { shadowBlur: 8 } } }],
    })
  }

  // 3) 审核状态饼图
  if (statusChartRef.value) {
    statusIns = statusIns || echarts.init(statusChartRef.value)
    const colors = { pending: '#e6a23c', approved: '#67c23a', rejected: '#f56c6c' }
    const labels = { pending: '待审核', approved: '已通过', rejected: '已拒绝' }
    statusIns.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        data: auditStats.value.by_status.map(s => ({
          name: labels[s.status] || s.status,
          value: s.count,
          itemStyle: { color: colors[s.status] || '#409eff' },
        })),
        label: { formatter: '{b}: {c} ({d}%)' },
      }],
    })
  }

  // 4) 审核日趋势堆叠柱
  if (auditTrendChartRef.value) {
    auditTrendIns = auditTrendIns || echarts.init(auditTrendChartRef.value)
    const days = auditStats.value.by_day
    auditTrendIns.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: ['待审核', '已通过', '已拒绝'], top: 0 },
      grid: { left: 50, right: 20, top: 30, bottom: 30 },
      xAxis: { type: 'category', data: days.map(d => d.date) },
      yAxis: { type: 'value' },
      series: [
        { name: '待审核', type: 'bar', stack: 'audit', data: days.map(d => d.pending), itemStyle: { color: '#e6a23c' } },
        { name: '已通过', type: 'bar', stack: 'audit', data: days.map(d => d.approved), itemStyle: { color: '#67c23a' } },
        { name: '已拒绝', type: 'bar', stack: 'audit', data: days.map(d => d.rejected), itemStyle: { color: '#f56c6c' } },
      ],
    })
  }
}

function handleResize() {
  activityIns?.resize(); heatmapIns?.resize(); statusIns?.resize(); auditTrendIns?.resize()
}

function onRefresh(e) { loadAll() }

onMounted(() => {
  loadAll()
  window.addEventListener('resize', handleResize)
  window.addEventListener('admin-refresh', onRefresh)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('admin-refresh', onRefresh)
  activityIns?.dispose(); heatmapIns?.dispose(); statusIns?.dispose(); auditTrendIns?.dispose()
})
</script>

<style scoped>
.ao-root { padding: 0; }
.ao-h { margin-top: 0; color: var(--text-color); }
.ao-stat-row { margin-bottom: 16px; }
.ao-stat-card {
  background: var(--card-bg); padding: 12px 16px; border-radius: 4px;
  margin-bottom: 12px; box-shadow: var(--card-shadow);
}
.ao-stat-label { font-size: 12px; color: var(--text-color-secondary); }
.ao-stat-value { font-size: 22px; font-weight: 700; margin-top: 4px; color: var(--text-color); }
.ao-charts { margin-bottom: 16px; }
.ao-chart-card {
  background: var(--bg-color-secondary); padding: 12px; border-radius: 4px;
  margin-bottom: 12px; min-height: 340px;
}
.ao-chart-card h4 { margin: 0 0 8px 0; font-size: 14px; color: var(--text-color); }
.ao-chart { height: 320px; }
</style>
