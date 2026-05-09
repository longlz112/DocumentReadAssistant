<template>
  <el-container class="admin-layout">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <el-icon size="24"><Setting /></el-icon>
        <span>管理后台</span>
      </div>
      <el-menu :default-active="activeMenu" router background-color="#1a237e" text-color="#c5cae9" active-text-color="#ffffff">
        <el-menu-item index="/admin/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>数据概览</span>
        </el-menu-item>
        <el-menu-item index="/admin/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/papers">
          <el-icon><Document /></el-icon>
          <span>论文管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/monitor">
          <el-icon><Monitor /></el-icon>
          <span>系统监控</span>
        </el-menu-item>
        <el-menu-item index="/admin/llm">
          <el-icon><Cpu /></el-icon>
          <span>大模型消耗</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span class="page-title">{{ pageTitle }}</span>
        <div class="header-right">
          <span class="username">{{ adminUsername }}</span>
          <el-button type="danger" plain size="small" @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Setting, DataAnalysis, User, Document, Monitor, Cpu } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const adminUsername = localStorage.getItem('admin_username') || '管理员'
const activeMenu = computed(() => route.path)
const titleMap = {
  '/admin/dashboard': '数据概览',
  '/admin/users': '用户管理',
  '/admin/papers': '论文管理',
  '/admin/monitor': '系统监控',
  '/admin/llm': '大模型消耗',
}
const pageTitle = computed(() => titleMap[route.path] || '管理后台')

function logout() {
  localStorage.removeItem('admin_token')
  localStorage.removeItem('admin_username')
  router.push('/admin/login')
}
</script>

<style scoped>
.admin-layout {
  height: 100vh;
}
.sidebar {
  background: #1a237e;
  display: flex;
  flex-direction: column;
}
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  color: #fff;
  font-size: 16px;
  font-weight: bold;
  border-bottom: 1px solid #283593;
}
.el-menu {
  border-right: none;
  flex: 1;
}
.header {
  background: #fff;
  border-bottom: 1px solid #eee;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 60px;
}
.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.username {
  color: #606266;
  font-size: 14px;
}
.main-content {
  background: #f5f7fa;
  overflow-y: auto;
}
</style>
