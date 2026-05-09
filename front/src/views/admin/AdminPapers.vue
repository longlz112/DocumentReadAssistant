<template>
  <div>
    <el-card shadow="never" class="filter-card">
      <el-row :gutter="12" align="middle">
        <el-col :span="8">
          <el-input v-model="filters.search" placeholder="搜索标题/作者/关键词" clearable prefix-icon="Search" @keyup.enter="fetchPapers" />
        </el-col>
        <el-col :span="3">
          <el-select v-model="filters.is_processed" placeholder="处理状态" clearable style="width:100%">
            <el-option label="已处理" value="true" />
            <el-option label="未处理" value="false" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="filters.meta_confirmed" placeholder="元数据" clearable style="width:100%">
            <el-option label="已确认" value="true" />
            <el-option label="未确认" value="false" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-input v-model="filters.year" placeholder="年份" clearable />
        </el-col>
        <el-col :span="5">
          <el-button type="primary" @click="fetchPapers">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
          <el-button type="success" :disabled="!selectedIds.length" @click="batchConfirm">批量确认元数据</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="12" style="margin-top:12px">
      <el-col :span="16">
        <el-card shadow="never">
          <el-table
            :data="papers"
            v-loading="loading"
            stripe
            @selection-change="(rows) => selectedIds = rows.map(r => r.id)"
          >
            <el-table-column type="selection" width="42" />
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column label="标题" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ row.meta_title !== '无' ? row.meta_title : row.title }}</template>
            </el-table-column>
            <el-table-column prop="meta_authors" label="作者" width="120" show-overflow-tooltip />
            <el-table-column prop="meta_year" label="年份" width="70" />
            <el-table-column label="处理" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_processed ? 'success' : 'warning'" size="small">
                  {{ row.is_processed ? '完成' : '待处理' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="元数据" width="80">
              <template #default="{ row }">
                <el-tag :type="row.meta_confirmed ? 'success' : 'info'" size="small">
                  {{ row.meta_confirmed ? '已确认' : '未确认' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="username" label="上传者" width="90" />
            <el-table-column label="上传时间" min-width="150">
              <template #default="{ row }">{{ formatDate(row.uploaded_at) }}</template>
            </el-table-column>
          </el-table>
          <el-pagination
            style="margin-top:16px;justify-content:flex-end;display:flex"
            :current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="total, prev, pager, next"
            @current-change="(p) => { page = p; fetchPapers() }"
          />
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <span>热门研究领域 TOP50</span>
          </template>
          <div ref="kwChartEl" style="height:420px" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import adminApi from '../../api/admin'

const papers = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filters = ref({ search: '', is_processed: '', meta_confirmed: '', year: '' })
const selectedIds = ref([])
const kwChartEl = ref(null)

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

async function fetchPapers() {
  loading.value = true
  try {
    const res = await adminApi.getPapers({ page: page.value, page_size: pageSize.value, ...filters.value })
    papers.value = res.data.results
    total.value = res.data.total
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.value = { search: '', is_processed: '', meta_confirmed: '', year: '' }
  page.value = 1
  fetchPapers()
}

async function batchConfirm() {
  try {
    const res = await adminApi.batchUpdatePapers({ ids: selectedIds.value, action: 'confirm_meta' })
    ElMessage.success(`已确认 ${res.data.updated} 篇论文元数据`)
    fetchPapers()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

async function loadKeywords() {
  try {
    const res = await adminApi.getKeywords()
    const data = res.data
    await nextTick()
    const chart = echarts.init(kwChartEl.value)
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { top: 10, right: 20, bottom: 10, left: 10, containLabel: true },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: data.slice(0, 20).map(d => d.keyword).reverse(),
        axisLabel: { fontSize: 11, width: 80, overflow: 'truncate' },
      },
      series: [{
        type: 'bar', data: data.slice(0, 20).map(d => d.count).reverse(),
        itemStyle: { color: '#409eff' },
      }],
    })
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => { fetchPapers(); loadKeywords() })
</script>

<style scoped>
.filter-card { border-radius: 8px; }
</style>
