<template>
  <div>
    <el-alert
      v-if="llmStats.today?.alert"
      title="⚠ 今日 Token 消耗已超过阈值！"
      type="warning"
      show-icon
      :closable="false"
      style="margin-bottom:12px"
    />

    <el-row :gutter="16" class="stat-row">
      <el-col :span="6" v-for="card in summaryCards" :key="card.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:12px">
      <el-col :span="14">
        <el-card shadow="never">
          <template #header><span>Token 消耗趋势（近7天）</span></template>
          <div ref="trendChartEl" style="height:240px" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never">
          <template #header><span>操作类型分布</span></template>
          <div ref="opChartEl" style="height:240px" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top:12px">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>调用记录</span>
          <el-tag type="info">共 {{ totalRecords }} 条</el-tag>
        </div>
      </template>
      <el-table :data="records" v-loading="recordsLoading" stripe size="small">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="时间" min-width="160">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" width="120" />
        <el-table-column prop="operation" label="操作" width="120" />
        <el-table-column prop="input_tokens" label="输入" width="80" />
        <el-table-column prop="output_tokens" label="输出" width="80" />
        <el-table-column prop="total_tokens" label="总计" width="80">
          <template #default="{ row }">
            <span :style="{ color: row.total_tokens > 2000 ? '#f56c6c' : '#303133' }">
              {{ row.total_tokens }}
            </span>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        style="margin-top:12px;justify-content:flex-end;display:flex"
        :current-page="page"
        :page-size="pageSize"
        :total="totalRecords"
        layout="total, prev, pager, next"
        @current-change="(p) => { page = p; fetchRecords() }"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import adminApi from '../../api/admin'

const llmStats = ref({ overall: {}, today: {}, trend: [], op_distribution: [] })
const records = ref([])
const recordsLoading = ref(false)
const totalRecords = ref(0)
const page = ref(1)
const pageSize = ref(20)
const trendChartEl = ref(null)
const opChartEl = ref(null)

const summaryCards = computed(() => {
  const o = llmStats.value.overall || {}
  const t = llmStats.value.today || {}
  return [
    { label: '总调用次数', value: o.calls ?? '-' },
    { label: '总 Token 消耗', value: o.total_tokens ?? '-' },
    { label: '今日调用', value: t.calls ?? '-' },
    { label: '今日 Token', value: `${t.total_tokens ?? '-'} / ${t.daily_limit ?? '-'}` },
  ]
})

function formatDate(iso) {
  return iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }) : '-'
}

async function fetchStats() {
  try {
    const res = await adminApi.getLLMStats()
    llmStats.value = res.data
    await nextTick()

    const trend = res.data.trend || []
    const tChart = echarts.init(trendChartEl.value)
    tChart.setOption({
      legend: { data: ['Token 总量', '调用次数'], top: 0 },
      grid: { top: 30, right: 50, bottom: 30, left: 60 },
      xAxis: { type: 'category', data: trend.map(d => d.date) },
      yAxis: [
        { type: 'value', name: 'Tokens' },
        { type: 'value', name: '次数', splitLine: { show: false } },
      ],
      series: [
        { name: 'Token 总量', type: 'bar', data: trend.map(d => d.total_tokens), itemStyle: { color: '#409eff' } },
        { name: '调用次数', type: 'line', yAxisIndex: 1, data: trend.map(d => d.calls), itemStyle: { color: '#e6a23c' } },
      ],
    })

    const opDist = res.data.op_distribution || []
    const opChart = echarts.init(opChartEl.value)
    opChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, left: 'center', type: 'scroll' },
      series: [{
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['50%', '42%'],
        data: opDist.map(d => ({ name: d.operation || 'unknown', value: d.calls })),
        label: { show: false },
      }],
    })
  } catch (e) {
    console.error(e)
  }
}

async function fetchRecords() {
  recordsLoading.value = true
  try {
    const res = await adminApi.getLLMRecords({ page: page.value, page_size: pageSize.value })
    records.value = res.data.results
    totalRecords.value = res.data.total
  } catch (e) {
    console.error(e)
  } finally {
    recordsLoading.value = false
  }
}

onMounted(() => { fetchStats(); fetchRecords() })
</script>

<style scoped>
.stat-row { margin-bottom: 4px; }
.stat-card { text-align: center; }
.stat-value { font-size: 26px; font-weight: 700; color: #303133; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
</style>
