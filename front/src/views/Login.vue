<template>
  <div class="login-container">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <h2>大模型论文阅读助手</h2>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="登录" name="login"></el-tab-pane>
        <el-tab-pane label="注册" name="register"></el-tab-pane>
      </el-tabs>

      <el-form :model="form" label-width="80px" class="mt-4">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" @keyup.enter="handleSubmit" />
        </el-form-item>
        <el-button type="primary" class="w-100" @click="handleSubmit" :loading="loading">
          {{ activeTab === 'login' ? '登录' : '注册' }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElNotification } from 'element-plus'
import api from '../api'

const router = useRouter()
const activeTab = ref('login')
const loading = ref(false)
const form = ref({ username: '', password: '' })

// 格式化时间显示（可自定义）
const formatLastLogin = (isoString) => {
  if (!isoString) return '这是您第一次登录'
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

const handleSubmit = async () => {
  if (!form.value.username || !form.value.password) {
    return ElMessage.warning('请填写完整的用户名和密码')
  }
  loading.value = true
  try {
    const res = activeTab.value === 'login'
        ? await api.login(form.value)
        : await api.register(form.value)

    // 保存 Token 和用户名
    localStorage.setItem('token', res.data.token)
    localStorage.setItem('username', res.data.username)

    // 显示上次登录时间（仅在登录时显示）
    if (activeTab.value === 'login' && res.data.last_login !== undefined) {
      const lastLoginText = formatLastLogin(res.data.last_login)
      ElNotification({
        title: '登录成功',
        message: `上次登录时间：${lastLoginText}`,
        type: 'success',
        duration: 5000,
      })
    } else {
      ElMessage.success('登录成功')
    }

    router.push('/')
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '请求失败，请检查账号密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f3f4f6;
}
.box-card {
  width: 400px;
}
.card-header {
  text-align: center;
}
.mt-4 { margin-top: 1rem; }
.w-100 { width: 100%; }
</style>
