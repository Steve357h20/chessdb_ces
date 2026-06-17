<template>
  <div class="at-root">
    <div class="at-toolbar">
      <el-radio-group v-model="hours" size="small" @change="loadAll">
        <el-radio-button :value="1">1h</el-radio-button>
        <el-radio-button :value="6">6h</el-radio-button>
        <el-radio-button :value="24">24h</el-radio-button>
        <el-radio-button :value="72">3d</el-radio-button>
        <el-radio-button :value="168">7d</el-radio-button>
      </el-radio-group>
      <span class="at-summary" v-if="summary">
        窗口内: {{ summary.total_requests }} 次请求 / {{ summary.unique_users }} 独立用户 / 错误 {{ summary.error_count }} ({{ ((summary.error_rate || 0) * 100).toFixed(2) }}%)
      </span>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <div class="at-card">
          <h4>端点 × 时段 热力图（TOP {{ heatmap.x_axis.length }}）</h4>
          <div ref="heatmapRef" class="at-chart"></div>
        </div>
      </el-col>
      <el-col :xs="24" :md="12">
        <div class="at-card">
          <h4>用户活跃度对比（游客/登录/管理员）</h4>
          <div ref="activityRef" class="at-chart"></div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <div class="at-card">
          <h4>端点延迟 P50/P95/P99（散点图：横=调用量，纵=P95 延迟）</h4>
          <div ref="healthRef" class="at-chart"></div>
        </div>
      </el-col>
      <el-col :xs="24" :md="12">
        <div class="at-card">
          <h4>写操作 API 排行（POST/PUT/DELETE/PATCH）</h4>
          <div ref="writeRef" class="at-chart"></div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import {
  getAnalyticsHeatmap, getAnalyticsUserActivity,
  getAnalyticsEndpointHealth, getAnalyticsDbChanges, getTrafficSummary,
} from '@/api/admin'

const hours = ref(24)
const summary = ref(null)
const heatmap = ref({ x_axis: [], y_axis: [], matrix: [] })
const activity = ref({ series: { guest: [], user: [], admin: [] } })
const health = ref({ endpoints: [] })
const writes = ref({ write_apis: [] })

const heatmapRef = ref(null)
const activityRef = ref(null)
const healthRef = ref(null)
const writeRef = ref(null)
let heatmapIns = null, activityIns = null, healthIns = null, writeIns = null

async function loadAll() {
  const [sm, hm, ua, eh, dc] = await Promise.all([
    getTrafficSummary({ hours: hours.value }).catch(() => ({ summary: {} })),
    getAnalyticsHeatmap({ hours: hours.value, top: 20 }).catch(() => ({ x_axis: [], y_axis: [], matrix: [] })),
    getAnalyticsUserActivity({ hours: hours.value }).catch(() => ({ series: { guest: [], user: [], admin: [] } })),
    getAnalyticsEndpointHealth({ hours: hours.value }).catch(() => ({ endpoints: [] })),
    getAnalyticsDbChanges({ days: 14 }).catch(() => ({ write_apis: [] })),
  ])
  summary.value = (sm.data || sm).summary
  heatmap.value = hm.data || hm
  activity.value = ua.data || ua
  health.value = eh.data || eh
  writes.value = dc.data || dc
  await nextTick()
  renderCharts()
}

function renderCharts() {
  if (heatmapRef.value) {
    heatmapIns = heatmapIns || echarts.init(heatmapRef.value)
    const x = heatmap.value.x_axis.map(p => p.replace(/^\/api\//, ''))
    const max = Math.max(1, ...heatmap.value.matrix.map(c => c[2]))
    heatmapIns.setOption({
      tooltip: { position: 'top', formatter: (p) => `${x[p.data[0]]} @ ${p.data[1]}h → ${p.data[2]} 次` },
      grid: { left: 110, right: 20, top: 10, bottom: 60 },
      xAxis: { type: 'category', data: x, axisLabel: { rotate: 45, fontSize: 9 }, splitArea: { show: true } },
      yAxis: { type: 'category', data: heatmap.value.y_axis.map(h => `${h}h`), splitArea: { show: true } },
      visualMap: { min: 0, max, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, itemWidth: 12, itemHeight: 80 },
      series: [{ name: '调用', type: 'heatmap', data: heatmap.value.matrix, emphasis: { itemStyle: { shadowBlur: 8 } } }],
    })
  }

  if (activityRef.value) {
    activityIns = activityIns || echarts.init(activityRef.value)
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
        { name: '游客', type: 'line', smooth: true, data: xAll.map(h => find(guest, h)), itemStyle: { color: '#909399' } },
        { name: '登录用户', type: 'line', smooth: true, data: xAll.map(h => find(user, h)), itemStyle: { color: '#409eff' } },
        { name: '管理员', type: 'line', smooth: true, data: xAll.map(h => find(admin, h)), itemStyle: { color: '#f56c6c' } },
      ],
    })
  }

  if (healthRef.value) {
    healthIns = healthIns || echarts.init(healthRef.value)
    const eps = health.value.endpoints
    const data = eps.map(e => ({
      name: e.path.replace(/^\/api\//, ''),
      value: [e.count, e.p95_ms, e.p50_ms, e.p99_ms],
    }))
    healthIns.setOption({
      tooltip: {
        formatter: (p) => `${p.data.name}<br/>调用: ${p.data.value[0]}<br/>P50: ${p.data.value[2]}ms<br/>P95: ${p.data.value[1]}ms<br/>P99: ${p.data.value[3]}ms`,
      },
      grid: { left: 60, right: 20, top: 10, bottom: 50 },
      xAxis: { type: 'value', name: '调用量', nameLocation: 'center', nameGap: 28, type: 'log' },
      yAxis: { type: 'value', name: 'P95 (ms)', nameLocation: 'center', nameGap: 38 },
      series: [{
        type: 'scatter',
        symbolSize: (v) => Math.max(6, Math.min(30, Math.sqrt(v[0]))),
        data,
        itemStyle: { color: '#409eff', opacity: 0.7 },
        emphasis: { itemStyle: { borderColor: '#f56c6c', borderWidth: 2 } },
      }],
    })
  }

  if (writeRef.value) {
    writeIns = writeIns || echarts.init(writeRef.value)
    const items = (writes.value.write_apis || []).slice(0, 15).reverse()
    const colors = { POST: '#67c23a', PUT: '#e6a23c', DELETE: '#f56c6c', PATCH: '#409eff' }
    writeIns.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 130, right: 20, top: 10, bottom: 30 },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: items.map(w => `${w.method} ${w.path.replace(/^\/api\//, '')}`),
        axisLabel: { fontSize: 10 },
      },
      series: [{
        type: 'bar',
        data: items.map(w => ({ value: w.count, itemStyle: { color: colors[w.method] || '#409eff' } })),
      }],
    })
  }
}

function handleResize() { heatmapIns?.resize(); activityIns?.resize(); healthIns?.resize(); writeIns?.resize() }
function onRefresh(e) { loadAll() }

onMounted(() => {
  loadAll()
  window.addEventListener('resize', handleResize)
  window.addEventListener('admin-refresh', onRefresh)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('admin-refresh', onRefresh)
  heatmapIns?.dispose(); activityIns?.dispose(); healthIns?.dispose(); writeIns?.dispose()
})
</script>

<style scoped>
.at-toolbar { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.at-summary { color: var(--text-color-regular); font-size: 13px; }
.at-card { background: var(--bg-color-secondary); padding: 12px; border-radius: 4px; margin-bottom: 12px; min-height: 360px; }
.at-card h4 { margin: 0 0 8px 0; font-size: 14px; color: var(--text-color); }
.at-chart { height: 340px; }
</style>
