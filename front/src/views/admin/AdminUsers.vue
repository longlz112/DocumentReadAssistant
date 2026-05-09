<template>
  <div>
    <el-card shadow="never" class="filter-card">
      <el-row :gutter="12" align="middle">
        <el-col :span="8">
          <el-input v-model="filters.search" placeholder="搜索用户名/邮箱" clearable prefix-icon="Search" @keyup.enter="fetchUsers" />
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.is_active" placeholder="活跃状态" clearable style="width:100%">
            <el-option label="活跃" value="true" />
            <el-option label="停用" value="false" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.is_staff" placeholder="管理员" clearable style="width:100%">
            <el-option label="是管理员" value="true" />
            <el-option label="普通用户" value="false" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="fetchUsers">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card shadow="never" style="margin-top:12px">
      <el-table :data="users" v-loading="loading" stripe style="width:100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip />
        <el-table-column prop="first_name" label="昵称" width="100" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '活跃' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="权限" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_superuser" type="danger" size="small">超级管理员</el-tag>
            <el-tag v-else-if="row.is_staff" type="warning" size="small">管理员</el-tag>
            <el-tag v-else type="info" size="small">普通用户</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="paper_count" label="论文数" width="80" />
        <el-table-column label="注册时间" min-width="160">
          <template #default="{ row }">{{ formatDate(row.date_joined) }}</template>
        </el-table-column>
        <el-table-column label="最后登录" min-width="160">
          <template #default="{ row }">{{ row.last_login ? formatDate(row.last_login) : '从未' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              :type="row.is_active ? 'danger' : 'success'"
              @click="toggleActive(row)"
              :disabled="row.is_superuser"
            >
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
            <el-button
              size="small"
              :type="row.is_staff ? 'warning' : 'primary'"
              @click="toggleStaff(row)"
              :disabled="row.is_superuser"
              plain
            >
              {{ row.is_staff ? '撤销管理' : '设为管理' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        style="margin-top:16px;justify-content:flex-end;display:flex"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="(p) => { page = p; fetchUsers() }"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import adminApi from '../../api/admin'

const users = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filters = ref({ search: '', is_active: '', is_staff: '' })

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

async function fetchUsers() {
  loading.value = true
  try {
    const res = await adminApi.getUsers({
      page: page.value,
      page_size: pageSize.value,
      ...filters.value,
    })
    users.value = res.data.results
    total.value = res.data.total
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.value = { search: '', is_active: '', is_staff: '' }
  page.value = 1
  fetchUsers()
}

async function toggleActive(row) {
  const action = row.is_active ? '禁用' : '启用'
  await ElMessageBox.confirm(`确定要${action}用户 "${row.username}" 吗？`, '提示', { type: 'warning' })
  try {
    await adminApi.updateUser(row.id, { is_active: !row.is_active })
    row.is_active = !row.is_active
    ElMessage.success(`已${action}`)
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  }
}

async function toggleStaff(row) {
  const action = row.is_staff ? '撤销管理员权限' : '设为管理员'
  await ElMessageBox.confirm(`确定要${action} "${row.username}" 吗？`, '提示', { type: 'warning' })
  try {
    await adminApi.updateUser(row.id, { is_staff: !row.is_staff })
    row.is_staff = !row.is_staff
    ElMessage.success('操作成功')
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.filter-card { border-radius: 8px; }
</style>
