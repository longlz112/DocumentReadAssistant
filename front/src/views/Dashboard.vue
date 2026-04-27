<template>
  <el-container class="dashboard">
    <!-- 左侧论文列表侧边栏 -->
    <el-aside width="300px" class="aside">
      <div class="sidebar-header">
        <h3>论文库</h3>
        <div class="header-actions">
          <el-upload
              action=""
              :http-request="customUpload"
              :show-file-list="false"
              accept=".pdf"
          >
            <el-button type="primary" :icon="Plus" size="small" :loading="uploading">上传</el-button>
          </el-upload>
          <el-tooltip :content="multiMode ? '退出多选' : '多论文对比'" placement="bottom">
            <el-button
                :type="multiMode ? 'warning' : 'default'"
                :icon="Grid"
                size="small"
                @click="toggleMultiMode"
            />
          </el-tooltip>
        </div>
      </div>

      <!-- 多选模式提示条 -->
      <div v-if="multiMode" class="multi-mode-bar">
        <span>已选 {{ selectedPapers.length }} 篇</span>
        <el-button
            type="primary"
            size="small"
            :disabled="selectedPapers.length < 2"
            @click="openMultiAnalysis"
        >开始对比分析</el-button>
      </div>

      <el-menu :default-active="activePaperId" class="paper-menu">
        <el-menu-item
            v-for="paper in papers"
            :key="paper.id"
            :index="paper.id.toString()"
            @click="handlePaperClick(paper)"
            :class="{ 'is-selected-multi': isSelectedForMulti(paper) }"
        >
          <el-checkbox
              v-if="multiMode"
              :model-value="isSelectedForMulti(paper)"
              @change="togglePaperSelection(paper)"
              @click.stop
              class="multi-checkbox"
          />
          <el-icon v-else><Document /></el-icon>
          <span class="paper-title" :title="paper.title">{{ paper.title }}</span>
          <el-tag v-if="!paper.is_processed" size="small" type="warning" class="ms-auto">解析中</el-tag>
          <el-tag v-else-if="!paper.meta_confirmed" size="small" type="info" class="ms-auto">待确认</el-tag>
        </el-menu-item>
      </el-menu>

      <div class="logout-btn">
        <el-button text :icon="User" @click="$router.push('/user-center')">{{ username }}</el-button>
        <el-button text @click="logout">退出登录</el-button>
      </div>
    </el-aside>

    <!-- 右侧主体内容 -->
    <el-main class="main-content">
      <!-- 多论文分析面板 -->
      <MultiAnalysis
          v-if="showMultiAnalysis"
          :selected-papers="selectedPapers"
          @remove-paper="removePaperFromSelection"
      />
      <!-- 单篇论文工作区 -->
      <Workspace v-else-if="currentPaper" :paper="currentPaper" />
      <div v-else class="empty-state">
        <el-empty :description="multiMode ? '请在左侧勾选至少两篇论文，然后点击「开始对比分析」' : '请在左侧选择或上传一篇论文'" />
      </div>
    </el-main>

    <!-- 元数据确认弹窗 -->
    <el-dialog
        v-model="metaDialogVisible"
        title="论文元数据确认"
        width="600px"
        :close-on-click-modal="false"
        :close-on-press-escape="false"
        :show-close="false"
    >
      <p class="meta-hint">以下是自动提取的元数据，请确认或修正后保存。</p>
      <el-form :model="metaForm" label-width="90px" label-position="left">
        <el-form-item label="标题">
          <el-input v-model="metaForm.meta_title" :disabled="!metaEditing" />
        </el-form-item>
        <el-form-item label="作者">
          <el-input v-model="metaForm.meta_authors" :disabled="!metaEditing" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="metaForm.meta_keywords" :disabled="!metaEditing" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="metaForm.meta_abstract" type="textarea" :rows="4" :disabled="!metaEditing" />
        </el-form-item>
        <el-form-item label="期刊/会议">
          <el-input v-model="metaForm.meta_journal" :disabled="!metaEditing" />
        </el-form-item>
        <el-form-item label="发表年份">
          <el-input v-model="metaForm.meta_year" :disabled="!metaEditing" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="meta-dialog-footer">
          <el-button @click="handleReextract" :loading="reextracting">重新提取</el-button>
          <el-button @click="metaEditing = !metaEditing" :type="metaEditing ? 'warning' : 'default'">
            {{ metaEditing ? '取消编辑' : '手动修改' }}
          </el-button>
          <el-button type="primary" @click="handleConfirmMeta" :loading="metaSaving">确认保存</el-button>
        </div>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Document, Grid, User } from '@element-plus/icons-vue'
import api from '../api'
import Workspace from './Workspace.vue'
import MultiAnalysis from './MultiAnalysis.vue'

const router = useRouter()
const papers = ref([])
const activePaperId = ref('')
const currentPaper = ref(null)
const uploading = ref(false)
const username = ref(localStorage.getItem('username') || '')

// 多选相关状态
const multiMode = ref(false)
const selectedPapers = ref([])
const showMultiAnalysis = ref(false)

// 元数据弹窗状态
const metaDialogVisible = ref(false)
const metaEditing = ref(false)
const metaSaving = ref(false)
const reextracting = ref(false)
const metaPaperId = ref(null)
const metaForm = ref({
  meta_title: '', meta_authors: '', meta_keywords: '',
  meta_abstract: '', meta_journal: '', meta_year: '',
})

const fetchPapers = async () => {
  try {
    const res = await api.getPapers()
    papers.value = res.data
  } catch (error) {
    ElMessage.error('获取论文列表失败')
  }
}

const checkPaperStatus = async (paperId) => {
  while (true) {
    try {
      const res = await api.pollingStatus(paperId)
      if (res.data.status === 'processed') {
        await fetchPapers()
        // 解析完成后弹出元数据确认窗
        openMetaDialog(paperId)
        break
      }
    } catch (error) {
      console.log(error)
    }
    await new Promise(resolve => setTimeout(resolve, 1000))
  }
}

const openMetaDialog = async (paperId) => {
  try {
    const res = await api.getMetadata(paperId)
    metaPaperId.value = paperId
    Object.assign(metaForm.value, res.data)
    metaEditing.value = false
    metaDialogVisible.value = true
  } catch (e) {
    console.error('获取元数据失败', e)
  }
}

const handleReextract = async () => {
  reextracting.value = true
  try {
    const res = await api.reextractMetadata(metaPaperId.value)
    Object.assign(metaForm.value, res.data)
    metaEditing.value = false
    ElMessage.success('重新提取完成')
  } catch (e) {
    ElMessage.error('重新提取失败')
  } finally {
    reextracting.value = false
  }
}

const handleConfirmMeta = async () => {
  metaSaving.value = true
  try {
    // 确保发送 meta_confirmed 字段
    const payload = {
      ...metaForm.value,
      meta_confirmed: true
    }
    await api.updateMetadata(metaPaperId.value, payload)
    ElMessage.success('元数据已保存')
    metaDialogVisible.value = false
    metaEditing.value = false
    metaPaperId.value = null
    await fetchPapers()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    metaSaving.value = false
  }
}

const customUpload = async (options) => {
  const file = options.file
  const formData = new FormData()
  formData.append('file', file)
  formData.append('title', file.name.replace('.pdf', ''))

  uploading.value = true
  try {
    const res = await api.uploadPaper(formData)
    ElMessage.success('上传成功,后台正在处理中...')
    await fetchPapers()
    // 获取新上传论文的 ID 并开始轮询
    const newPaperId = res.data.id || res.data.paper_id
    if (newPaperId) {
      checkPaperStatus(newPaperId)
    }
  } catch (error) {
    ElMessage.error('上传失败')
    if (error.response?.data?.error) {
      ElMessage.error(error.response.data.error)
    }
  } finally {
    uploading.value = false
  }
}

const selectPaper = (paper) => {
  activePaperId.value = paper.id.toString()
  currentPaper.value = paper
  showMultiAnalysis.value = false
}

const handlePaperClick = (paper) => {
  if (multiMode.value) {
    togglePaperSelection(paper)
  } else {
    selectPaper(paper)
  }
}

// 多选模式
const toggleMultiMode = () => {
  multiMode.value = !multiMode.value
  if (!multiMode.value) {
    selectedPapers.value = []
    showMultiAnalysis.value = false
  }
}

const isSelectedForMulti = (paper) => {
  return selectedPapers.value.some(p => p.id === paper.id)
}

const togglePaperSelection = (paper) => {
  const idx = selectedPapers.value.findIndex(p => p.id === paper.id)
  if (idx === -1) {
    selectedPapers.value.push(paper)
  } else {
    selectedPapers.value.splice(idx, 1)
  }
}

const removePaperFromSelection = (paper) => {
  selectedPapers.value = selectedPapers.value.filter(p => p.id !== paper.id)
  if (selectedPapers.value.length < 2) {
    showMultiAnalysis.value = false
  }
}

const openMultiAnalysis = () => {
  if (selectedPapers.value.length < 2) {
    return ElMessage.warning('请至少选择两篇论文')
  }
  showMultiAnalysis.value = true
  currentPaper.value = null
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
.header-actions { display: flex; gap: 6px; align-items: center; }

.multi-mode-bar {
  padding: 8px 15px;
  background: #ecf5ff;
  border-bottom: 1px solid #d9ecff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #409eff;
}

.paper-menu { flex-grow: 1; overflow-y: auto; border-right: none; }
.paper-title {
  display: inline-block;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ms-auto { margin-left: auto; }
.multi-checkbox { margin-right: 8px; flex-shrink: 0; }
.is-selected-multi { background-color: #ecf5ff !important; }

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
.meta-hint { margin: 0 0 12px; color: #606266; font-size: 13px; }
.meta-dialog-footer { display: flex; justify-content: flex-end; gap: 8px; }
</style>

