<template>
  <el-container class="dashboard">
    <!-- 左侧论文列表侧边栏 -->
    <el-aside width="300px" class="aside">
      <div class="sidebar-header">
        <h3>论文库</h3>
        <el-upload
            action=""
            :http-request="customUpload"
            :show-file-list="false"
            accept=".pdf"
        >
          <el-button type="primary" :icon="Plus" size="small" :loading="uploading">上传论文</el-button>
        </el-upload>
      </div>

      <el-menu :default-active="activePaperId" class="paper-menu">
        <el-menu-item
            v-for="paper in papers"
            :key="paper.id"
            :index="paper.id.toString()"
            @click="selectPaper(paper)"
        >
          <el-icon><Document /></el-icon>
          <span class="paper-title" :title="paper.title">{{ paper.title }}</span>
          <el-tag v-if="!paper.is_processed" size="small" type="warning" class="ms-auto">解析中</el-tag>
        </el-menu-item>
      </el-menu>

      <div class="logout-btn">
        <el-button text @click="logout">退出登录 ({{ username }})</el-button>
      </div>
    </el-aside>

    <!-- 右侧主体内容 -->
    <el-main class="main-content">
      <Workspace v-if="currentPaper" :paper="currentPaper" />
      <div v-else class="empty-state">
        <el-empty description="请在左侧选择或上传一篇论文" />
      </div>
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Document } from '@element-plus/icons-vue'
import api from '../api'
import Workspace from './Workspace.vue'

const router = useRouter()
const papers = ref([])
const activePaperId = ref('')
const currentPaper = ref(null)
const uploading = ref(false)
const username = ref(localStorage.getItem('username') || '')

const fetchPapers = async () => {
  try {
    const res = await api.getPapers()
    papers.value = res.data
  } catch (error) {
    ElMessage.error('获取论文列表失败')
  }
}

//轮询是否处理结束
const checkPaperStatus = async (checkPapers) => {
  for (let check_paper of checkPapers.value) {
    console.log(check_paper)
    while (true) {
      try{
        const res = await api.pollingStatus(check_paper.id);
        if (res.data.status === 'processed') {
          await fetchPapers()
          break;
        }
      }catch (error){
        console.log(error)
      }finally {
        // 等待1秒后继续下一次检查, 降低频率
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
  }
}



const customUpload = async (options) => {
  const file = options.file
  const formData = new FormData()
  formData.append('file', file)
  formData.append('title', file.name.replace('.pdf', ''))

  uploading.value = true
  try {
    await api.uploadPaper(formData)
    ElMessage.success('上传成功，后台正在处理中...')
    await fetchPapers() // 等待列表刷新完成
    checkPaperStatus(papers)
  } catch (error) {
    ElMessage.error('上传失败')
    ElMessage.error(error.response.data.error)
  } finally {
    uploading.value = false
  }
}

const selectPaper = (paper) => {
  activePaperId.value = paper.id.toString()
  currentPaper.value = paper
}

const logout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  router.push('/login')
}

onMounted(() => {
  fetchPapers()
})
</script>

<style scoped>
.dashboard { height: 100vh; }
.aside {
  background-color: #fff;
  border-right: 1px solid #dcdfe6;
  display: flex;
  flex-direction: column;
}
.sidebar-header {
  padding: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #dcdfe6;
}
.sidebar-header h3 { margin: 0; font-size: 16px; }
.paper-menu { flex-grow: 1; overflow-y: auto; border-right: none; }
.paper-title {
  display: inline-block;
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ms-auto { margin-left: auto; }
.logout-btn {
  padding: 10px;
  text-align: center;
  border-top: 1px solid #dcdfe6;
}
.main-content { padding: 0; background-color: #f5f7fa; }
.empty-state {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>
