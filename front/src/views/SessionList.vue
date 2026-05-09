<template>
  <div class="session-list-wrap">
    <div class="session-list-container">
      <div class="page-header">
        <el-button :icon="ArrowLeft" text @click="$router.push('/user-center')">返回个人中心</el-button>
        <h2>会话记录</h2>
      </div>

      <el-card shadow="never">
        <div v-if="loading" class="loading-box">
          <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        </div>

        <el-empty v-else-if="sessions.length === 0" description="暂无会话记录" />

        <div v-else>
          <el-table :data="sessions" style="width: 100%" stripe>
            <el-table-column label="会话标题" min-width="200">
              <template #default="{ row }">
                <div style="display:flex;align-items:center;gap:6px">
                  <el-tag v-if="row.session_type === 'multi'" size="small" type="warning">多论文</el-tag>
                  <el-tag v-else size="small" type="primary">单论文</el-tag>
                  <el-link type="primary" @click="$router.push(`/sessions/${row.id}`)">
                    {{ row.title }}
                  </el-link>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="消息数" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ row.message_count }} 条</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="170" align="center">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="最后更新" width="170" align="center">
              <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button
                  :icon="Download"
                  size="small"
                  text
                  title="导出 Markdown"
                  :loading="exportingId === row.id"
                  @click="exportSession(row)"
                />
                <el-popconfirm title="确认删除该会话？" @confirm="deleteSession(row.id)">
                  <template #reference>
                    <el-button :icon="Delete" type="danger" size="small" text />
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-box">
            <el-pagination
              background
              layout="total, prev, pager, next"
              :total="total"
              :page-size="pageSize"
              :current-page="currentPage"
              @current-change="handlePageChange"
            />
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Delete, Loading, Download } from '@element-plus/icons-vue'
import api from '../api/index.js'
import { exportSessionAsMarkdown } from '../utils/export.js'

const sessions = ref([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const exportingId = ref(null)

onMounted(() => fetchSessions())

async function fetchSessions(page = 1) {
  loading.value = true
  try {
    const res = await api.getSessions(page, pageSize.value)
    sessions.value = res.data.results
    total.value = res.data.count
    currentPage.value = page
  } catch {
    ElMessage.error('获取会话列表失败')
  } finally {
    loading.value = false
  }
}

function handlePageChange(page) {
  fetchSessions(page)
}

async function deleteSession(id) {
  try {
    await api.deleteSession(id)
    ElMessage.success('已删除')
    fetchSessions(currentPage.value)
  } catch {
    ElMessage.error('删除失败')
  }
}

async function exportSession(row) {
  exportingId.value = row.id
  try {
    const res = await api.getSession(row.id)
    exportSessionAsMarkdown(res.data)
  } catch {
    ElMessage.error('导出失败')
  } finally {
    exportingId.value = null
  }
}

function formatTime(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>

<style scoped>
.session-list-wrap {
  min-height: 100vh;
  background: #f5f7fa;
  padding: 24px;
}

.session-list-container {
  max-width: 960px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.loading-box {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.pagination-box {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
