<template>
  <div class="stats-page">
    <div class="sp-header">
      <h2>数据分析</h2>
      <p class="sp-desc">ELO等级分 vs 对局步数 关联分析</p>
    </div>

    <el-card v-if="loading" class="sp-chart-card">
      <div class="sp-loading">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <span>加载数据中...</span>
      </div>
    </el-card>

    <template v-else>
      <el-row :gutter="16" class="sp-summary">
        <el-col :xs="12" :sm="6">
          <el-statistic title="总对局数" :value="totalGames" />
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-statistic title="ELO范围" :value="eloRange" />
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-statistic title="平均步数" :value="avgMoves" :precision="1" />
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-statistic title="查询耗时" :value="queryTime" suffix="ms" />
        </el-col>
      </el-row>

      <el-card class="sp-chart-card">
        <template #header>
          <div class="sp-card-header">
            <span>ELO均分 vs 平均步数（按10分分桶）</span>
            <el-radio-group v-model="chartMode" size="small">
              <el-radio-button value="line">折线</el-radio-button>
              <el-radio-button value="scatter">散点</el-radio-button>
              <el-radio-button value="both">叠加</el-radio-button>
            </el-radio-group>
          </div>
        </template>
        <v-chart
          ref="mainChartRef"
          :option="mainChartOption"
          :autoresize="true"
          style="height: 450px; width: 100%"
        />
      </el-card>

      <el-card class="sp-chart-card">
        <template #header>
          <div class="sp-card-header">
            <span>对局分布分析</span>
            <el-radio-group v-model="scatterMode" size="small">
              <el-radio-button value="heatmap">热力密度图</el-radio-button>
              <el-radio-button value="scatter">散点图</el-radio-button>
              <el-radio-button value="boxplot">箱线图</el-radio-button>
            </el-radio-group>
          </div>
        </template>
        <v-chart
          ref="scatterChartRef"
          :option="scatterChartOption"
          :autoresize="true"
          style="height: 500px; width: 100%"
        />
      </el-card>

      <el-card class="sp-chart-card">
        <template #header>
          <div class="sp-card-header">
            <span>步数分布直方图</span>
          </div>
        </template>
        <v-chart
          ref="histChartRef"
          :option="histChartOption"
          :autoresize="true"
          style="height: 400px; width: 100%"
        />
      </el-card>

      <div class="stats-section">
        <div class="stats-section-header">
          <h2>开局统计分析</h2>
          <el-radio-group v-model="openingChartMode" size="small">
            <el-radio-button value="winrate">胜率排行</el-radio-button>
            <el-radio-button value="frequency">使用分布</el-radio-button>
            <el-radio-button value="elo">ELO关系</el-radio-button>
          </el-radio-group>
        </div>
        <div class="stats-opening-content">
          <div v-if="openingChartMode === 'winrate'" style="height:500px">
            <v-chart :option="openingWinrateOption" autoresize />
          </div>
          <div v-else-if="openingChartMode === 'frequency'" class="stats-chart-row">
            <div style="height:400px;flex:1">
              <v-chart :option="openingCategoryOption" autoresize />
            </div>
            <div style="flex:1;max-width:500px">
              <el-table :data="openingStats.slice(0,10)" max-height="380" size="small">
                <el-table-column prop="eco_code" label="ECO" width="70" />
                <el-table-column prop="name" label="开局名称" show-overflow-tooltip />
                <el-table-column prop="total" label="对局数" width="80" sortable />
              </el-table>
            </div>
          </div>
          <div v-else-if="openingChartMode === 'elo'" style="height:400px">
            <v-chart :option="openingEloOption" autoresize />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import request from '@/api/request'
import { useThemeStore } from '@/store/themeStore'

const themeStore = useThemeStore()

const loading = ref(true)
const buckets = ref([])
const scatter = ref([])
const densityGrid = ref([])
const distribution = ref([])
const totalGames = ref(0)
const queryTime = ref(0)
const chartMode = ref('both')
const scatterMode = ref('heatmap')

const openingStats = ref([])
const categoryStats = ref([])
const eloOpeningStats = ref([])
const openingChartMode = ref('winrate')

const mainChartRef = ref(null)
const scatterChartRef = ref(null)
const histChartRef = ref(null)

// 最小二乘法线性回归
function linearRegression(points) {
  const n = points.length
  if (n < 2) return null
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0
  for (const [x, y] of points) {
    sumX += x; sumY += y; sumXY += x * y; sumX2 += x * x
  }
  const denom = n * sumX2 - sumX * sumX
  if (denom === 0) return null
  const slope = (n * sumXY - sumX * sumY) / denom
  const intercept = (sumY - slope * sumX) / n
  // R^2
  const yMean = sumY / n
  let ssTot = 0, ssRes = 0
  for (const [x, y] of points) {
    ssTot += (y - yMean) ** 2
    ssRes += (y - (slope * x + intercept)) ** 2
  }
  const r2 = ssTot === 0 ? 0 : 1 - ssRes / ssTot
  return { slope, intercept, r2 }
}

// 计算预测残差并按 IQR 剔除离群点（针对 x 轴为 ELO 的桶点）
function filterOutliers(points, k = 1.5) {
  if (points.length < 4) return { kept: points, removed: [], bounds: null }
  const ys = points.map(p => p[1]).sort((a, b) => a - b)
  const q1 = ys[Math.floor(ys.length * 0.25)]
  const q3 = ys[Math.floor(ys.length * 0.75)]
  const iqr = q3 - q1
  const lower = q1 - k * iqr
  const upper = q3 + k * iqr
  const kept = []
  const removed = []
  for (const p of points) {
    if (p[1] >= lower && p[1] <= upper) {
      kept.push(p)
    } else {
      removed.push(p)
    }
  }
  return { kept, removed, bounds: { lower, upper, q1, q3, iqr } }
}

const eloRange = computed(() => {
  if (!buckets.value.length) return '-'
  const elos = buckets.value.map(b => b.avg_elo)
  return `${Math.min(...elos)} - ${Math.max(...elos)}`
})

const avgMoves = computed(() => {
  if (!buckets.value.length) return 0
  const total = buckets.value.reduce((s, b) => s + b.avg_moves * b.game_count, 0)
  const count = buckets.value.reduce((s, b) => s + b.game_count, 0)
  return count > 0 ? total / count : 0
})

const mainChartOption = computed(() => {
  const isDark = themeStore.isDark
  const textColor = isDark ? '#e5eaf3' : '#303133'
  const splitLineColor = isDark ? '#363637' : '#e8e8e8'

  if (!buckets.value.length) {
    return { title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: isDark ? '#a3a6ad' : '#999' } } }
  }

  const xData = buckets.value.map(b => b.avg_elo)
  const yData = buckets.value.map(b => b.avg_moves)
  const sizeData = buckets.value.map(b => b.game_count)

  // 线性拟合：先按 IQR 剔除离群点，再用稳健数据重算
  const rawPoints = xData.map((x, i) => [x, yData[i]])
  const { kept, removed, bounds } = filterOutliers(rawPoints, 1.5)
  const fitRaw = linearRegression(rawPoints)            // 全量拟合（参考）
  const fit = linearRegression(kept.length >= 2 ? kept : rawPoints)  // 稳健拟合（用于趋势线）
  // 离群标记
  const removedSet = new Set(removed.map(p => `${p[0]}_${p[1]}`))

  const series = []

  // 趋势线 + 预测延伸
  if (fit) {
    const xMin = Math.min(...xData)
    const xMax = Math.max(...xData)
    const xRange = xMax - xMin || 1
    // 预测延伸 20% 范围
    const predMin = xMin - xRange * 0.1
    const predMax = xMax + xRange * 0.2
    const predStep = xRange / 50
    const trendData = []
    const predData = []
    for (let x = predMin; x <= predMax; x += predStep) {
      const y = fit.slope * x + fit.intercept
      if (x < xMin) {
        predData.push([x, y])
      } else if (x > xMax) {
        if (predData.length === 0) predData.push([xData[xData.length - 1], fit.slope * xData[xData.length - 1] + fit.intercept])
        predData.push([x, y])
      } else {
        trendData.push([x, y])
      }
    }
    // 确保趋势线覆盖数据范围端点
    if (trendData.length > 0) {
      trendData[0] = [xMin, fit.slope * xMin + fit.intercept]
      trendData[trendData.length - 1] = [xMax, fit.slope * xMax + fit.intercept]
    }

    const removedInfo = (removed.length > 0 && fitRaw)
      ? `\u00A0\u00A0剔除 ${removed.length}/${rawPoints.length} 离群点 (IQR ${bounds.lower.toFixed(1)}~${bounds.upper.toFixed(1)})`
      : ''
    const fitLabel = `y = ${fit.slope >= 0 ? '' : '-'}${Math.abs(fit.slope).toFixed(4)}x ${fit.intercept >= 0 ? '+' : '-'} ${Math.abs(fit.intercept).toFixed(2)}  (R\u00B2=${fit.r2.toFixed(4)})${removedInfo}`

    series.push({
      name: `线性拟合 ${fitLabel}`,
      type: 'line',
      data: trendData,
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 2, color: '#f56c6c', type: 'dashed' },
      itemStyle: { color: '#f56c6c' },
      tooltip: {
        formatter: (params) => {
          return `线性拟合<br/>ELO: ${params.data[0].toFixed(0)}<br/>预测步数: ${params.data[1].toFixed(1)}<br/>${fitLabel}`
        },
      },
      z: 10,
    })

    if (predData.length > 0) {
      series.push({
        name: '预测延伸',
        type: 'line',
        data: predData,
        smooth: false,
        symbol: 'none',
        lineStyle: { width: 2, color: '#f56c6c', type: [6, 6] },
        itemStyle: { color: '#f56c6c', opacity: 0.5 },
        tooltip: {
          formatter: (params) => {
            return `预测延伸<br/>ELO: ${params.data[0].toFixed(0)}<br/>预测步数: ${params.data[1].toFixed(1)}`
          },
        },
        z: 9,
      })
    }
  }

  if (chartMode.value === 'line' || chartMode.value === 'both') {
    series.push({
      name: '平均步数',
      type: 'line',
      data: xData.map((x, i) => [x, yData[i]]),
      smooth: 0.4,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: { width: 3, color: '#409eff' },
      itemStyle: { color: '#409eff' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(64,158,255,0.25)' },
            { offset: 1, color: 'rgba(64,158,255,0.02)' },
          ],
        },
      },
    })
  }

  if (chartMode.value === 'scatter' || chartMode.value === 'both') {
    // 把散点拆为正常点 + 离群点两个 series，离群点用醒目红色
    const normalPts = []
    const outlierPts = []
    xData.forEach((x, i) => {
      const isOutlier = removedSet.has(`${x}_${yData[i]}`)
      const pt = [x, yData[i], sizeData[i], isOutlier]
      if (isOutlier) outlierPts.push(pt); else normalPts.push(pt)
    })
    series.push({
      name: '对局数（点大小=对局数量）',
      type: 'scatter',
      data: normalPts,
      symbolSize: (val) => Math.max(6, Math.sqrt(val[2]) * 1.5),
      itemStyle: { color: 'rgba(230,162,60,0.7)', borderColor: '#e6a23c', borderWidth: 1 },
    })
    if (outlierPts.length > 0) {
      series.push({
        name: `离群点（已剔除 ${outlierPts.length}）`,
        type: 'scatter',
        data: outlierPts,
        symbolSize: (val) => Math.max(8, Math.sqrt(val[2]) * 1.5),
        itemStyle: { color: 'rgba(245,108,108,0.85)', borderColor: '#c45656', borderWidth: 2 },
        symbol: 'diamond',
        tooltip: {
          formatter: (params) => {
            const d = params.data
            return `⚠️ 离群点（未参与拟合）<br/>ELO均分: ${d[0]}<br/>平均步数: ${d[1]}<br/>对局数: ${d[2]}`
          },
        },
        z: 11,
      })
    }
  }

  return {
    backgroundColor: 'transparent',
    textStyle: { color: textColor },
    tooltip: {
      trigger: 'item',
      backgroundColor: isDark ? '#1d1d1d' : '#fff',
      borderColor: isDark ? '#4c4d4f' : '#e4e7ed',
      textStyle: { color: textColor },
      formatter: (params) => {
        const d = params.data
        if (d.length === 3) {
          return `ELO均分: ${d[0]}<br/>平均步数: ${d[1]}<br/>对局数: ${d[2]}（点越大对局越多）`
        }
        return `ELO均分: ${d[0]}<br/>平均步数: ${d[1]}`
      },
    },
    grid: { left: 70, right: 30, top: 30, bottom: 60 },
    xAxis: {
      type: 'value',
      name: 'ELO均分',
      nameLocation: 'center',
      nameGap: 30,
      nameTextStyle: { color: textColor },
      min: (value) => Math.floor(value.min / 100) * 100,
      axisLabel: { fontSize: 11, color: textColor },
      axisLine: { lineStyle: { color: splitLineColor } },
    },
    yAxis: {
      type: 'value',
      name: '平均步数',
      nameLocation: 'center',
      nameGap: 45,
      nameTextStyle: { color: textColor },
      min: 0,
      axisLabel: { fontSize: 11, color: textColor },
      axisLine: { lineStyle: { color: splitLineColor } },
      splitLine: { lineStyle: { type: 'dashed', color: splitLineColor } },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, bottom: 5, height: 18, borderColor: isDark ? '#4c4d4f' : '#ddd', textStyle: { color: textColor } },
    ],
    series,
  }
})

const heatmapOption = computed(() => {
  const isDark = themeStore.isDark
  const textColor = isDark ? '#e5eaf3' : '#303133'

  if (!densityGrid.value.length) {
    return { title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: isDark ? '#a3a6ad' : '#999' } } }
  }

  const data = densityGrid.value
  const eloSet = new Set(data.map(d => d[0]))
  const moveSet = new Set(data.map(d => d[1]))
  const eloList = [...eloSet].sort((a, b) => a - b)
  const moveList = [...moveSet].sort((a, b) => a - b)

  const eloMap = {}
  eloList.forEach((e, i) => { eloMap[e] = i })
  const moveMap = {}
  moveList.forEach((m, i) => { moveMap[m] = i })

  const heatData = data.map(d => [eloMap[d[0]], moveMap[d[1]], d[2]])
  const maxCount = Math.max(...data.map(d => d[2]))

  return {
    backgroundColor: 'transparent',
    textStyle: { color: textColor },
    tooltip: {
      formatter: (params) => {
        const d = params.data
        const elo = eloList[d[0]]
        const move = moveList[d[1]]
        return `ELO: ${elo}-${elo + 49}<br/>步数: ${move}-${move + 9}<br/>对局数: ${d[2]}`
      },
      backgroundColor: isDark ? '#1d1d1d' : '#fff',
      borderColor: isDark ? '#4c4d4f' : '#e4e7ed',
      textStyle: { color: textColor },
    },
    grid: { left: 100, right: 120, top: 30, bottom: 60 },
    xAxis: {
      type: 'category',
      data: eloList.map(e => `${e}`),
      name: 'ELO均分（每50分一格）',
      nameLocation: 'center',
      nameGap: 35,
      nameTextStyle: { color: textColor },
      axisLabel: { fontSize: 10, rotate: 45, color: textColor },
      axisLine: { lineStyle: { color: isDark ? '#4c4d4f' : '#e8e8e8' } },
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: moveList.map(m => `${m}-${m + 9}`),
      name: '总步数（每10步一格）',
      nameLocation: 'center',
      nameGap: 80,
      nameTextStyle: { color: textColor },
      axisLabel: { fontSize: 10, color: textColor },
      axisLine: { lineStyle: { color: isDark ? '#4c4d4f' : '#e8e8e8' } },
      splitArea: { show: true },
    },
    visualMap: {
      min: 0,
      max: maxCount,
      calculable: true,
      orient: 'vertical',
      right: 10,
      top: 'center',
      itemWidth: 14,
      itemHeight: 140,
      text: [`${maxCount}`, '0'],
      inRange: {
        color: ['#e0f3db', '#a8ddb5', '#7bccc4', '#4eb3d3', '#2b8cbe', '#08589e'],
      },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, bottom: 5, height: 18 },
      { type: 'inside', yAxisIndex: 0 },
    ],
    series: [{
      name: '对局密度',
      type: 'heatmap',
      data: heatData,
      label: {
        show: heatData.length < 200,
        fontSize: 9,
        formatter: (p) => p.data[2] > 0 ? p.data[2] : '',
      },
      emphasis: {
        itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' },
      },
    }],
  }
})

const scatterRawOption = computed(() => {
  const isDark = themeStore.isDark
  const textColor = isDark ? '#e5eaf3' : '#303133'
  const splitLineColor = isDark ? '#363637' : '#e8e8e8'

  if (!scatter.value.length) {
    return { title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: isDark ? '#a3a6ad' : '#999' } } }
  }

  const scatterData = scatter.value.map(s => [s.avg_elo, s.total_moves, s.elo_gap, s.result])
  const gapMax = Math.max(400, ...scatter.value.map(s => s.elo_gap || 0))
  const resultLabels = { '1-0': '白胜', '0-1': '黑胜', '1/2-1/2': '和棋' }

  return {
    backgroundColor: 'transparent',
    textStyle: { color: textColor },
    tooltip: {
      formatter: (params) => {
        const d = params.data
        const resultLabel = resultLabels[d[3]] || d[3]
        return `ELO均分: ${d[0]}<br/>步数: ${d[1]}<br/>ELO差距: ${d[2]}<br/>结果: ${resultLabel}`
      },
      backgroundColor: isDark ? '#1d1d1d' : '#fff',
      borderColor: isDark ? '#4c4d4f' : '#e4e7ed',
      textStyle: { color: textColor },
    },
    grid: { left: 70, right: 100, top: 30, bottom: 60 },
    xAxis: {
      type: 'value',
      name: 'ELO均分',
      nameLocation: 'center',
      nameGap: 30,
      nameTextStyle: { color: textColor },
      axisLabel: { fontSize: 11, color: textColor },
      axisLine: { lineStyle: { color: splitLineColor } },
    },
    yAxis: {
      type: 'value',
      name: '总步数',
      nameLocation: 'center',
      nameGap: 45,
      nameTextStyle: { color: textColor },
      min: 0,
      axisLabel: { fontSize: 11, color: textColor },
      axisLine: { lineStyle: { color: splitLineColor } },
      splitLine: { lineStyle: { type: 'dashed', color: splitLineColor } },
    },
    visualMap: {
      type: 'continuous',
      min: 0,
      max: gapMax,
      dimension: 2,
      text: [`差距 ${gapMax}+`, '差距 0'],
      inRange: {
        color: ['#67c23a', '#409eff', '#e6a23c', '#f56c6c', '#c45656'],
      },
      right: 10,
      top: 'center',
      itemWidth: 14,
      itemHeight: 120,
      calculable: true,
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, bottom: 5, height: 18 },
      { type: 'inside', yAxisIndex: 0 },
    ],
    series: [{
      name: '对局',
      type: 'scatter',
      data: scatterData,
      symbolSize: 4,
      itemStyle: { opacity: 0.65 },
      emphasis: { itemStyle: { opacity: 1, borderWidth: 1, borderColor: '#333' } },
      large: true,
      largeThreshold: 2000,
    }],
  }
})

const boxplotOption = computed(() => {
  const isDark = themeStore.isDark
  const textColor = isDark ? '#e5eaf3' : '#303133'
  const splitLineColor = isDark ? '#363637' : '#e8e8e8'

  if (!distribution.value.length) {
    return { title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: isDark ? '#a3a6ad' : '#999' } } }
  }

  const dist = distribution.value
  const categories = dist.map(d => `${d.elo_bucket}`)

  const meanData = dist.map(d => d.mean)
  const lowerData = dist.map(d => Math.max(0, d.mean - d.std))
  const upperData = dist.map(d => d.mean + d.std)
  const minData = dist.map(d => d.min)
  const maxData = dist.map(d => d.max)

  return {
    backgroundColor: 'transparent',
    textStyle: { color: textColor },
    tooltip: {
      trigger: 'item',
      backgroundColor: isDark ? '#1d1d1d' : '#fff',
      borderColor: isDark ? '#4c4d4f' : '#e4e7ed',
      textStyle: { color: textColor },
      formatter: (params) => {
        const idx = params.dataIndex
        const info = dist[idx]
        if (!info) return ''
        if (params.seriesName === '均值 ± 标准差') {
          return `ELO: ${info.elo_bucket}-${info.elo_bucket + 49}<br/>` +
            `对局数: ${info.count}<br/>` +
            `均值: ${info.mean}<br/>` +
            `标准差: ${info.std}<br/>` +
            `范围: ${Math.max(0, info.mean - info.std).toFixed(1)} ~ ${(info.mean + info.std).toFixed(1)}`
        }
        if (params.seriesName === '极值范围') {
          return `ELO: ${info.elo_bucket}-${info.elo_bucket + 49}<br/>` +
            `最小步数: ${info.min}<br/>` +
            `最大步数: ${info.max}`
        }
        return `ELO: ${info.elo_bucket}-${info.elo_bucket + 49}<br/>均值: ${info.mean}`
      },
    },
    legend: {
      data: ['均值 ± 标准差', '极值范围', '均值线'],
      top: 5,
      textStyle: { color: textColor },
    },
    grid: { left: 100, right: 30, top: 50, bottom: 80 },
    xAxis: {
      type: 'category',
      data: categories,
      name: 'ELO均分（每50分一桶）',
      nameLocation: 'center',
      nameGap: 40,
      nameTextStyle: { color: textColor },
      axisLabel: { fontSize: 10, rotate: 45, color: textColor },
      axisLine: { lineStyle: { color: splitLineColor } },
    },
    yAxis: {
      type: 'value',
      name: '总步数',
      nameLocation: 'center',
      nameGap: 50,
      nameTextStyle: { color: textColor },
      min: 0,
      axisLabel: { fontSize: 11, color: textColor },
      axisLine: { lineStyle: { color: splitLineColor } },
      splitLine: { lineStyle: { type: 'dashed', color: splitLineColor } },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, bottom: 5, height: 18, borderColor: isDark ? '#4c4d4f' : '#ddd', textStyle: { color: textColor } },
    ],
    series: [
      {
        name: '极值范围',
        type: 'custom',
        renderItem: (params, api) => {
          const x = api.coord([api.value(0), 0])[0]
          const yMin = api.coord([0, api.value(1)])[1]
          const yMax = api.coord([0, api.value(2)])[1]
          const width = 12
          return {
            type: 'group',
            children: [
              {
                type: 'rect',
                shape: { x: x - width / 2, y: yMax, width: width, height: yMin - yMax },
                style: { fill: 'rgba(103,194,58,0.15)', stroke: '#67c23a', lineWidth: 1 },
              },
              {
                type: 'line',
                shape: { x1: x - width / 2, y1: yMin, x2: x + width / 2, y2: yMin },
                style: { stroke: '#67c23a', lineWidth: 2 },
              },
              {
                type: 'line',
                shape: { x1: x - width / 2, y1: yMax, x2: x + width / 2, y2: yMax },
                style: { stroke: '#67c23a', lineWidth: 2 },
              },
            ],
          }
        },
        data: categories.map((_, i) => [i, minData[i], maxData[i]]),
        z: 1,
      },
      {
        name: '均值 ± 标准差',
        type: 'custom',
        renderItem: (params, api) => {
          const x = api.coord([api.value(0), 0])[0]
          const yMean = api.coord([0, api.value(1)])[1]
          const yLower = api.coord([0, api.value(2)])[1]
          const yUpper = api.coord([0, api.value(3)])[1]
          const width = 24
          return {
            type: 'group',
            children: [
              {
                type: 'rect',
                shape: { x: x - width / 2, y: yUpper, width: width, height: yLower - yUpper },
                style: { fill: 'rgba(64,158,255,0.25)', stroke: '#409eff', lineWidth: 1.5 },
              },
              {
                type: 'line',
                shape: { x1: x - width / 2, y1: yMean, x2: x + width / 2, y2: yMean },
                style: { stroke: '#409eff', lineWidth: 3 },
              },
            ],
          }
        },
        data: categories.map((_, i) => [i, meanData[i], lowerData[i], upperData[i]]),
        z: 2,
      },
      {
        name: '均值线',
        type: 'line',
        data: meanData,
        smooth: 0.3,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2, color: '#e6a23c', type: 'dashed' },
        itemStyle: { color: '#e6a23c' },
        z: 3,
      },
      // 箱线图线性拟合趋势线（先按 IQR 剔除离群 ELO 桶）
      ...(function () {
        if (dist.length < 2) return []
        const pts = dist.map(d => [d.elo_bucket, d.mean])
        const { kept, removed, bounds } = filterOutliers(pts, 1.5)
        const fit = linearRegression(kept.length >= 2 ? kept : pts)
        if (!fit) return []
        const removedInfo = (removed.length > 0)
          ? `\u00A0\u00A0剔除 ${removed.length}/${pts.length} 离群点 (IQR ${bounds.lower.toFixed(1)}~${bounds.upper.toFixed(1)})`
          : ''
        const fitLabel = `y = ${fit.slope >= 0 ? '' : '-'}${Math.abs(fit.slope).toFixed(4)}x ${fit.intercept >= 0 ? '+' : '-'} ${Math.abs(fit.intercept).toFixed(2)}  (R\u00B2=${fit.r2.toFixed(4)})${removedInfo}`
        const trendData = categories.map((_, i) => fit.slope * dist[i].elo_bucket + fit.intercept)
        return [{
          name: `线性拟合 ${fitLabel}`,
          type: 'line',
          data: trendData,
          smooth: false,
          symbol: 'none',
          lineStyle: { width: 2, color: '#f56c6c', type: 'dashed' },
          itemStyle: { color: '#f56c6c' },
          tooltip: {
            formatter: (params) => {
              return `线性拟合<br/>ELO: ${dist[params.dataIndex].elo_bucket}<br/>预测均值: ${params.data.toFixed(1)}<br/>${fitLabel}`
            },
          },
          z: 4,
        }]
      })(),
      // 箱线图离群点高亮（红色菱形）
      ...(function () {
        if (dist.length < 4) return []
        const pts = dist.map(d => [d.elo_bucket, d.mean])
        const { removed } = filterOutliers(pts, 1.5)
        if (removed.length === 0) return []
        const catMap = new Map(categories.map((c, i) => [c, i]))
        const outlierData = removed.map(p => catMap.get(`${p[0]}`) ?? null).filter(i => i !== null)
        return [{
          name: `离群点（已剔除 ${outlierData.length}）`,
          type: 'scatter',
          data: outlierData,
          symbol: 'diamond',
          symbolSize: 12,
          itemStyle: { color: 'rgba(245,108,108,0.9)', borderColor: '#c45656', borderWidth: 2 },
          tooltip: {
            formatter: (params) => {
              const i = params.dataIndex
              return `⚠️ 离群点（未参与拟合）<br/>ELO: ${removed[i][0]}<br/>均值: ${removed[i][1].toFixed(1)}`
            },
          },
          z: 5,
        }]
      })(),
    ],
  }
})

const scatterChartOption = computed(() => {
  if (scatterMode.value === 'heatmap') return heatmapOption.value
  if (scatterMode.value === 'boxplot') return boxplotOption.value
  return scatterRawOption.value
})

const histChartOption = computed(() => {
  if (!scatter.value.length) {
    return { title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#999' } } }
  }

  const bins = {}
  const step = 10
  for (const s of scatter.value) {
    const bucket = Math.floor(s.total_moves / step) * step
    bins[bucket] = (bins[bucket] || 0) + 1
  }

  const sorted = Object.entries(bins).sort((a, b) => parseInt(a[0]) - parseInt(b[0]))
  const xData = sorted.map(([k]) => `${k}-${parseInt(k) + step - 1}`)
  const yData = sorted.map(([, v]) => v)

  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 70, right: 30, top: 30, bottom: 70 },
    xAxis: {
      type: 'category',
      data: xData,
      name: '步数区间',
      nameLocation: 'center',
      nameGap: 45,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      name: '对局数',
      nameLocation: 'center',
      nameGap: 50,
      axisLabel: { fontSize: 11 },
      splitLine: { lineStyle: { type: 'dashed', color: '#e8e8e8' } },
    },
    series: [{
      type: 'bar',
      data: yData,
      itemStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: '#409eff' },
            { offset: 1, color: 'rgba(64,158,255,0.4)' },
          ],
        },
        borderRadius: [3, 3, 0, 0],
      },
    }],
  }
})

const openingWinrateOption = computed(() => {
  const isDark = themeStore.isDark
  const textColor = isDark ? '#e5eaf3' : '#303133'
  const splitLineColor = isDark ? '#363637' : '#e8e8e8'

  if (!openingStats.value.length) {
    return { title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: isDark ? '#a3a6ad' : '#999' } } }
  }

  const stats = openingStats.value.slice(0, 15)
  const names = stats.map(s => s.name || s.eco_code)
  const whiteData = stats.map(s => s.white_win_rate || 0)
  const drawData = stats.map(s => s.draw_rate || 0)
  const blackData = stats.map(s => s.black_win_rate || 0)

  return {
    backgroundColor: 'transparent',
    textStyle: { color: textColor },
    tooltip: {
      trigger: 'axis',
      backgroundColor: isDark ? '#1d1d1d' : '#fff',
      borderColor: isDark ? '#4c4d4f' : '#e4e7ed',
      textStyle: { color: textColor },
      formatter: (params) => {
        const idx = params[0].dataIndex
        const s = stats[idx]
        let tip = `<b>${s.eco_code} ${s.name}</b><br/>`
        tip += `白胜率: ${s.white_win_rate}%<br/>`
        tip += `和棋率: ${s.draw_rate}%<br/>`
        tip += `黑胜率: ${s.black_win_rate}%<br/>`
        tip += `对局数: ${s.total}`
        return tip
      },
    },
    legend: {
      data: ['白方胜率', '和棋率', '黑方胜率'],
      top: 5,
      textStyle: { color: textColor },
    },
    grid: { left: 150, right: 30, top: 50, bottom: 30 },
    xAxis: {
      type: 'value',
      max: 100,
      name: '百分比 (%)',
      nameTextStyle: { color: textColor },
      axisLabel: { fontSize: 11, color: textColor, formatter: '{value}%' },
      axisLine: { lineStyle: { color: splitLineColor } },
      splitLine: { lineStyle: { type: 'dashed', color: splitLineColor } },
    },
    yAxis: {
      type: 'category',
      data: names,
      inverse: true,
      axisLabel: { fontSize: 10, color: textColor, width: 140, overflow: 'truncate' },
      axisLine: { lineStyle: { color: splitLineColor } },
    },
    series: [
      {
        name: '白方胜率',
        type: 'bar',
        stack: 'total',
        data: whiteData,
        itemStyle: { color: '#f56c6c' },
      },
      {
        name: '和棋率',
        type: 'bar',
        stack: 'total',
        data: drawData,
        itemStyle: { color: '#e6a23c' },
      },
      {
        name: '黑方胜率',
        type: 'bar',
        stack: 'total',
        data: blackData,
        itemStyle: { color: '#409eff' },
      },
    ],
  }
})

const openingCategoryOption = computed(() => {
  const isDark = themeStore.isDark
  const textColor = isDark ? '#e5eaf3' : '#303133'

  if (!categoryStats.value.length) {
    return { title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: isDark ? '#a3a6ad' : '#999' } } }
  }

  const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399']
  const pieData = categoryStats.value.map((c, i) => ({
    name: c.name || c.category,
    value: c.total,
    itemStyle: { color: colors[i % colors.length] },
  }))

  return {
    backgroundColor: 'transparent',
    textStyle: { color: textColor },
    tooltip: {
      trigger: 'item',
      backgroundColor: isDark ? '#1d1d1d' : '#fff',
      borderColor: isDark ? '#4c4d4f' : '#e4e7ed',
      textStyle: { color: textColor },
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: textColor },
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['40%', '50%'],
      data: pieData,
      emphasis: {
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' },
      },
      label: {
        color: textColor,
        formatter: '{b}\n{d}%',
      },
    }],
  }
})

const openingEloOption = computed(() => {
  const isDark = themeStore.isDark
  const textColor = isDark ? '#e5eaf3' : '#303133'

  if (!eloOpeningStats.value.length) {
    return { title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: isDark ? '#a3a6ad' : '#999' } } }
  }

  const stats = eloOpeningStats.value
  const catNames = [...new Set(stats.map(s => s.category))].sort()
  const eloBuckets = [...new Set(stats.map(s => s.elo_bucket))].sort((a, b) => a - b)

  const catMap = {}
  catNames.forEach((c, i) => { catMap[c] = i })
  const eloMap = {}
  eloBuckets.forEach((e, i) => { eloMap[e] = i })

  const heatData = stats.map(s => [catMap[s.category], eloMap[s.elo_bucket], s.total])
  const maxVal = Math.max(...stats.map(s => s.total))

  const catDisplayNames = catNames.map(c => {
    const found = categoryStats.value.find(cs => cs.category === c)
    return found ? found.name : c
  })

  return {
    backgroundColor: 'transparent',
    textStyle: { color: textColor },
    tooltip: {
      formatter: (params) => {
        const d = params.data
        const cat = catDisplayNames[d[0]]
        const elo = eloBuckets[d[1]]
        return `分类: ${cat}<br/>ELO范围: ${elo}-${elo + 499}<br/>对局数: ${d[2]}`
      },
      backgroundColor: isDark ? '#1d1d1d' : '#fff',
      borderColor: isDark ? '#4c4d4f' : '#e4e7ed',
      textStyle: { color: textColor },
    },
    grid: { left: 100, right: 120, top: 30, bottom: 60 },
    xAxis: {
      type: 'category',
      data: catDisplayNames,
      name: '开局分类',
      nameLocation: 'center',
      nameGap: 35,
      nameTextStyle: { color: textColor },
      axisLabel: { fontSize: 11, color: textColor },
      axisLine: { lineStyle: { color: isDark ? '#4c4d4f' : '#e8e8e8' } },
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: eloBuckets.map(e => `${e}`),
      name: 'ELO桶',
      nameLocation: 'center',
      nameGap: 60,
      nameTextStyle: { color: textColor },
      axisLabel: { fontSize: 10, color: textColor },
      axisLine: { lineStyle: { color: isDark ? '#4c4d4f' : '#e8e8e8' } },
      splitArea: { show: true },
    },
    visualMap: {
      min: 0,
      max: maxVal,
      calculable: true,
      orient: 'vertical',
      right: 10,
      top: 'center',
      itemWidth: 14,
      itemHeight: 140,
      text: [`${maxVal}`, '0'],
      inRange: {
        color: ['#e0f3db', '#a8ddb5', '#7bccc4', '#4eb3d3', '#2b8cbe', '#08589e'],
      },
      textStyle: { color: textColor },
    },
    series: [{
      name: '对局数',
      type: 'heatmap',
      data: heatData,
      label: {
        show: heatData.length < 50,
        fontSize: 9,
        color: textColor,
        formatter: (p) => p.data[2] > 0 ? p.data[2] : '',
      },
      emphasis: {
        itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' },
      },
    }],
  }
})

async function loadStats() {
  loading.value = true
  const start = performance.now()
  try {
    const res = await request.get('/games/stats/elo-vs-moves')
    const data = res.data || res
    buckets.value = data.buckets || []
    scatter.value = data.scatter || []
    densityGrid.value = data.density_grid || []
    distribution.value = data.distribution || []
    totalGames.value = data.total_games || 0
  } catch (e) {
    console.error('Failed to load stats:', e)
  } finally {
    queryTime.value = Math.round(performance.now() - start)
    loading.value = false
  }
}

async function loadOpeningStats() {
  try {
    const res = await request.get('/games/stats/openings')
    const data = res.data || res
    openingStats.value = data.openings || []
    categoryStats.value = data.categories || []
    eloOpeningStats.value = data.elo_openings || []
  } catch (e) {
    console.error('Failed to load opening stats:', e)
  }
}

onMounted(() => {
  loadStats()
  loadOpeningStats()
})
</script>

<style scoped>
.stats-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.sp-header {
  margin-bottom: 20px;
}

.sp-header h2 {
  margin: 0 0 4px;
  font-size: 22px;
  color: var(--text-color);
}

.sp-desc {
  margin: 0;
  color: var(--text-color-secondary);
  font-size: 14px;
}

.sp-summary {
  margin-bottom: 16px;
}

.sp-chart-card {
  margin-bottom: 16px;
}

.sp-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.sp-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 12px;
  color: var(--text-color-secondary);
}

.stats-section {
  margin-top: 24px;
  padding: 20px;
  background: var(--card-bg);
  border-radius: 8px;
}

.stats-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.stats-section-header h2 {
  margin: 0;
  font-size: 18px;
  color: var(--text-color);
}

.stats-chart-row {
  display: flex;
  gap: 20px;
}
</style>
