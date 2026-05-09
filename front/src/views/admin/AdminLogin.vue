<template>
  <div class="admin-login-page">
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <el-icon size="32"><Setting /></el-icon>
          <h2>管理员登录</h2>
        </div>
      </template>
      <el-form :model="form" @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" prefix-icon="User" placeholder="管理员用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" prefix-icon="Lock" placeholder="密码" show-password @keyup.enter="handleLogin" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" style="width:100%" @click="handleLogin">
            登录
          </el-button>
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Setting } from '@element-plus/icons-vue'
import adminApi from '../../api/admin'

const router = useRouter()
const form = ref({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  error.value = ''
  if (!form.value.username || !form.value.password) {
    error.value = '请填写用户名和密码'
    return
  }
  loading.value = true
  try {
    const res = await adminApi.login(form.value)
    localStorage.setItem('admin_token', res.data.token)
    localStorage.setItem('admin_username', res.data.username)
    router.push('/admin/dashboard')
  } catch (e) {
    console.log(error)
    error.value = e.response?.data?.error || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.admin-login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
}
.login-card {
  width: 400px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.card-header h2 {
  margin: 0;
  font-size: 20px;
}
</style>
