<template>
  <div>
    <!-- 筛选栏 -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">
        <el-input
          v-model="search"
          placeholder="搜索用户名或日志内容"
          clearable
          style="width:220px"
          @keyup.enter="fetchLogs(1)"
          @clear="fetchLogs(1)"
        />
        <el-select v-model="resultFilter" placeholder="操作结果" clearable style="width:130px" @change="fetchLogs(1)">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-button type="primary" @click="fetchLogs(1)">查询</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="logs" v-loading="loading" style="width:100%" stripe>
        <el-table-column prop="id" label="日志ID" width="80" align="center" />
        <el-table-column label="用户ID" width="80" align="center">
          <template #default="{ row }">{{ row.user_id ?? '—' }}</template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="log_info" label="日志信息" min-width="260" show-overflow-tooltip />
        <el-table-column label="操作时间" width="175" align="center">
          <template #default="{ row }">{{ formatTime(row.operation_time) }}</template>
        </el-table-column>
        <el-table-column label="操作结果" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.operation_result === 'success' ? 'success' : 'danger'" size="small">
              {{ row.operation_result === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div style="display:flex;justify-content:flex-end;margin-top:16px">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="currentPage"
          @current-change="fetchLogs"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import adminApi from '../../api/admin.js'

const logs = ref([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const search = ref('')
const resultFilter = ref('')

onMounted(() => fetchLogs(1))

async function fetchLogs(page = 1) {
  loading.value = true
  try {
    const res = await adminApi.getLogs({
      page,
      page_size: pageSize.value,
      search: search.value || undefined,
      result: resultFilter.value || undefined,
    })
    logs.value = res.data.results
    total.value = res.data.total
    currentPage.value = page
  } catch {
    ElMessage.error('获取日志失败')
  } finally {
    loading.value = false
  }
}

function formatTime(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}
</script>
