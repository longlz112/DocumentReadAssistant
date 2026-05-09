<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <div class="card-hd">
              <span>CPU 使用率</span>
              <el-tag size="small" :type="cpuType">{{ metrics.cpu?.percent ?? '-' }}%</el-tag>
            </div>
          </template>
          <el-progress :percentage="metrics.cpu?.percent ?? 0" :color="progressColor(metrics.cpu?.percent)" :stroke-width="18" />
          <div class="metric-detail">逻辑核心数：{{ metrics.cpu?.count ?? '-' }}</div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <div class="card-hd">
              <span>内存使用</span>
              <el-tag size="small" :type="memType">{{ metrics.memory?.percent ?? '-' }}%</el-tag>
            </div>
          </template>
          <el-progress :percentage="metrics.memory?.percent ?? 0" :color="progressColor(metrics.memory?.percent)" :stroke-width="18" />
          <div class="metric-detail">
            已用：{{ formatBytes(metrics.memory?.used) }} /
            总量：{{ formatBytes(metrics.memory?.total) }}
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <div class="card-hd">
              <span>磁盘使用</span>
              <el-tag size="small" :type="diskType">{{ metrics.disk?.percent ?? '-' }}%</el-tag>
            </div>
          </template>
          <el-progress :percentage="metrics.disk?.percent ?? 0" :color="progressColor(metrics.disk?.percent)" :stroke-width="18" />
          <div class="metric-detail">
            已用：{{ formatBytes(metrics.disk?.used) }} /
            总量：{{ formatBytes(metrics.disk?.total) }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top:16px">
      <template #header>
        <div class="card-hd">
          <span>网络 I/O（累计）</span>
          <el-button size="small" @click="fetchMetrics" :loading="loading">刷新</el-button>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="发送">{{ formatBytes(metrics.network?.bytes_sent) }}</el-descriptions-item>
        <el-descriptions-item label="接收">{{ formatBytes(metrics.network?.bytes_recv) }}</el-descriptions-item>
      </el-descriptions>
      <div style="color:#909399;font-size:12px;margin-top:8px">每 {{ interval }}s 自动刷新</div>
    </el-card>

    <el-card shadow="never" style="margin-top:16px">
      <template #header><span>CPU & 内存趋势（近20次采样）</span></template>
      <div ref="trendChartEl" style="height:220px" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import adminApi from '../../api/admin'

const metrics = ref({})
const loading = ref(false)
const interval = 5
const trendChartEl = ref(null)
let chart = null
let timer = null

const history = ref({ time: [], cpu: [], mem: [] })

const cpuType = computed(() => tagType(metrics.value.cpu?.percent))
const memType = computed(() => tagType(metrics.value.memory?.percent))
const diskType = computed(() => tagType(metrics.value.disk?.percent))

function tagType(pct) {
  if (pct == null) return 'info'
  return pct > 80 ? 'danger' : pct > 60 ? 'warning' : 'success'
}

function progressColor(pct) {
  if (pct == null) return '#909399'
  return pct > 80 ? '#f56c6c' : pct > 60 ? '#e6a23c' : '#67c23a'
}

function formatBytes(bytes) {
  if (bytes == null) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++ }
  return `${bytes.toFixed(1)} ${units[i]}`
}

async function fetchMetrics() {
  loading.value = true
  try {
    const res = await adminApi.getSystem()
    metrics.value = res.data
    const now = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    const h = history.value
    h.time.push(now)
    h.cpu.push(res.data.cpu?.percent ?? 0)
    h.mem.push(res.data.memory?.percent ?? 0)
    if (h.time.length > 20) { h.time.shift(); h.cpu.shift(); h.mem.shift() }
    updateChart()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function updateChart() {
  if (!chart) return
  const h = history.value
  chart.setOption({
    xAxis: { data: h.time },
    series: [{ data: h.cpu }, { data: h.mem }],
  })
}

onMounted(async () => {
  await fetchMetrics()
  await nextTick()
  chart = echarts.init(trendChartEl.value)
  chart.setOption({
    legend: { data: ['CPU%', '内存%'], top: 0 },
    grid: { top: 30, right: 20, bottom: 30, left: 40 },
    xAxis: { type: 'category', data: history.value.time },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
    series: [
      { name: 'CPU%', type: 'line', data: history.value.cpu, smooth: true, itemStyle: { color: '#409eff' } },
      { name: '内存%', type: 'line', data: history.value.mem, smooth: true, itemStyle: { color: '#e6a23c' } },
    ],
  })
  timer = setInterval(fetchMetrics, interval * 1000)
})

onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.card-hd { display: flex; justify-content: space-between; align-items: center; }
.metric-detail { font-size: 13px; color: #606266; margin-top: 10px; text-align: center; }
</style>
