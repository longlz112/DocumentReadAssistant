<template>
  <div class="dashboard">
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6" v-for="card in statCards" :key="card.label">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-icon" :style="{ background: card.color }">
              <el-icon size="24" color="#fff"><component :is="card.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ card.value }}</div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="charts-row">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>用户增长趋势（近7天）</span></template>
          <div ref="userChartEl" style="height:240px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>论文上传趋势（近7天）</span></template>
          <div ref="paperChartEl" style="height:240px" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="charts-row">
      <el-col :span="8">
        <el-card shadow="never">
          <template #header><span>用户状态分布</span></template>
          <div ref="userPieEl" style="height:220px" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <template #header><span>论文处理状态</span></template>
          <div ref="paperPieEl" style="height:220px" />
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="never" class="summary-card">
          <template #header><span>快速摘要</span></template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="今日新增用户">{{ stats.users?.today_new ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="近7天活跃用户">{{ stats.users?.recently_active ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="今日上传论文">{{ stats.papers?.today_new ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="待处理论文">{{ stats.papers?.pending ?? '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { User, Document, Check, Clock } from '@element-plus/icons-vue'
import adminApi from '../../api/admin'

const stats = ref({ users: {}, papers: {} })
const userChartEl = ref(null)
const paperChartEl = ref(null)
const userPieEl = ref(null)
const paperPieEl = ref(null)

const statCards = ref([
  { label: '总用户数', value: '-', icon: 'User', color: '#409eff' },
  { label: '活跃用户', value: '-', icon: 'Check', color: '#67c23a' },
  { label: '总论文数', value: '-', icon: 'Document', color: '#e6a23c' },
  { label: '今日新增用户', value: '-', icon: 'Clock', color: '#f56c6c' },
])

function makeLineOption(dates, values, name, color) {
  return {
    grid: { top: 20, right: 20, bottom: 30, left: 40 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      name, type: 'line', data: values, smooth: true,
      areaStyle: { opacity: 0.15 },
      itemStyle: { color },
      lineStyle: { color },
    }],
  }
}

function makePieOption(data, title) {
  return {
    title: { text: title, left: 'center', top: 0, textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, left: 'center' },
    series: [{ type: 'pie', radius: ['35%', '60%'], center: ['50%', '48%'], data }],
  }
}

onMounted(async () => {
  try {
    const res = await adminApi.getStats()
    stats.value = res.data
    const { users, papers, user_growth, paper_trend } = res.data

    statCards.value[0].value = users.total
    statCards.value[1].value = users.active
    statCards.value[2].value = papers.total
    statCards.value[3].value = users.today_new

    await nextTick()

    echarts.init(userChartEl.value).setOption(
      makeLineOption(user_growth.map(d => d.date), user_growth.map(d => d.count), '新增用户', '#409eff')
    )
    echarts.init(paperChartEl.value).setOption(
      makeLineOption(paper_trend.map(d => d.date), paper_trend.map(d => d.count), '上传论文', '#e6a23c')
    )
    echarts.init(userPieEl.value).setOption(makePieOption([
      { value: users.active, name: '活跃' },
      { value: users.total - users.active, name: '停用' },
    ]))
    echarts.init(paperPieEl.value).setOption(makePieOption([
      { value: papers.processed, name: '已处理' },
      { value: papers.pending, name: '待处理' },
    ]))
  } catch (e) {
    console.error(e)
  }
})
</script>

<style scoped>
.dashboard { padding: 4px; }
.stat-cards { margin-bottom: 16px; }
.stat-card { border-radius: 8px; }
.stat-content { display: flex; align-items: center; gap: 16px; padding: 4px 0; }
.stat-icon { width: 52px; height: 52px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.stat-value { font-size: 28px; font-weight: 700; color: #303133; line-height: 1; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
.charts-row { margin-bottom: 16px; }
</style>
