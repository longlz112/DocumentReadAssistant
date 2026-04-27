<template>
  <div class="user-center-wrap">
    <div class="user-center-container">
      <!-- 顶部导航 -->
      <div class="page-header">
        <el-button :icon="ArrowLeft" text @click="$router.push('/')">返回论文库</el-button>
        <h2>个人中心</h2>
      </div>

      <el-row :gutter="24">
        <!-- 左：头像 + 基本信息 -->
        <el-col :span="8">
          <el-card class="profile-card" shadow="never">
            <div class="avatar-section">
              <el-avatar :size="80" :src="avatarUrl">
                {{ (profile.first_name || profile.username || '?').charAt(0).toUpperCase() }}
              </el-avatar>
              <div class="user-meta">
                <div class="display-name">{{ profile.first_name || profile.username }}</div>
                <div class="username-sub">@{{ profile.username }}</div>
              </div>
            </div>
            <el-divider />
            <el-button type="primary" plain class="w-full" :icon="ChatLineRound" @click="$router.push('/sessions')">
              查看会话记录
            </el-button>
          </el-card>
        </el-col>

        <!-- 右：编辑表单 -->
        <el-col :span="16">
          <el-card shadow="never">
            <template #header>
              <span>编辑个人信息</span>
            </template>

            <el-form ref="formRef" :model="form" :rules="rules" label-width="90px" @submit.prevent>
              <el-form-item label="用户名">
                <el-input :value="profile.username" disabled />
              </el-form-item>

              <el-form-item label="昵称" prop="nickname">
                <el-input v-model="form.nickname" placeholder="设置昵称" maxlength="20" show-word-limit clearable />
              </el-form-item>

              <el-form-item label="邮箱" prop="email">
                <el-input v-model="form.email" placeholder="设置邮箱" clearable />
              </el-form-item>

              <el-divider content-position="left">修改密码（不修改则留空）</el-divider>

              <el-form-item label="当前密码" prop="old_password">
                <el-input v-model="form.old_password" type="password" placeholder="输入当前密码" show-password />
              </el-form-item>

              <el-form-item label="新密码" prop="new_password">
                <el-input v-model="form.new_password" type="password" placeholder="留空表示不修改" show-password />
              </el-form-item>

              <el-form-item label="确认密码" prop="confirm_password">
                <el-input v-model="form.confirm_password" type="password" placeholder="再次输入新密码" show-password />
              </el-form-item>

              <el-form-item>
                <el-button type="primary" :loading="saving" @click="handleSave">保存修改</el-button>
                <el-button @click="resetForm">重置</el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ChatLineRound } from '@element-plus/icons-vue'
import api from '../api/index.js'

const router = useRouter()
const formRef = ref(null)
const saving = ref(false)
const avatarUrl = ref('')

const profile = reactive({ username: '', first_name: '', email: '' })

const form = reactive({
  nickname: '',
  email: '',
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const validateConfirm = (rule, value, callback) => {
  if (form.new_password && value !== form.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  email: [{ type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }],
  confirm_password: [{ validator: validateConfirm, trigger: 'blur' }],
}

onMounted(async () => {
  try {
    const res = await api.getUserProfile()
    Object.assign(profile, res.data)
    form.nickname = res.data.first_name || ''
    form.email = res.data.email || ''
  } catch {
    ElMessage.error('获取用户信息失败')
  }
})

async function handleSave() {
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      const payload = {
        nickname: form.nickname,
        email: form.email,
      }
      if (form.new_password) {
        payload.old_password = form.old_password
        payload.new_password = form.new_password
      }
      const res = await api.updateUserProfile(payload)
      Object.assign(profile, res.data)

      // 密码修改后更新 token 并提示重新登录
      if (res.data.new_token) {
        localStorage.setItem('token', res.data.new_token)
        ElMessage.success('密码已修改，Token 已刷新')
      } else {
        ElMessage.success('保存成功')
      }

      form.old_password = ''
      form.new_password = ''
      form.confirm_password = ''
    } catch (err) {
      const msg = err.response?.data?.error || '保存失败，请稍后重试'
      ElMessage.error(msg)
    } finally {
      saving.value = false
    }
  })
}

function resetForm() {
  form.nickname = profile.first_name || ''
  form.email = profile.email || ''
  form.old_password = ''
  form.new_password = ''
  form.confirm_password = ''
  formRef.value?.clearValidate()
}
</script>

<style scoped>
.user-center-wrap {
  min-height: 100vh;
  background: #f5f7fa;
  padding: 24px;
}

.user-center-container {
  max-width: 900px;
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

.profile-card {
  text-align: center;
}

.avatar-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.display-name {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.username-sub {
  font-size: 13px;
  color: #909399;
}

.w-full {
  width: 100%;
}
</style>
