<template>
  <div class="session-detail-wrap">
    <div class="session-detail-container">
      <div class="page-header">
        <el-button :icon="ArrowLeft" text @click="$router.push('/sessions')">返回列表</el-button>
        <div class="title-area">
          <template v-if="editingTitle">
            <el-input
              v-model="editTitle"
              size="small"
              style="width: 240px"
              @keyup.enter="saveTitle"
              @blur="saveTitle"
              autofocus
            />
          </template>
          <template v-else>
            <h2>{{ session.title }}</h2>
            <el-button :icon="Edit" text size="small" @click="startEditTitle" />
          </template>
        </div>
        <el-button
          v-if="canContinue"
          type="primary"
          size="small"
          @click="continueSession"
        >继续对话</el-button>
        <el-button :icon="Download" size="small" @click="handleExport" :disabled="loading">
          导出 Markdown
        </el-button>
      </div>

      <el-card shadow="never" class="chat-card">
        <!-- 多论文分析时展示参与论文 -->
        <div v-if="session.session_type === 'multi' && session.paper_titles?.length" class="paper-tags-bar">
          <span class="bar-label">分析论文：</span>
          <el-tag v-for="t in session.paper_titles" :key="t" size="small" type="warning" style="margin-right:4px">{{ t }}</el-tag>
        </div>

        <div v-if="loading" class="loading-box">
          <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        </div>

        <el-empty v-else-if="!session.messages || session.messages.length === 0" description="该会话暂无消息" />

        <div v-else class="messages-list" ref="messagesRef">
          <div
            v-for="(msg, idx) in session.messages"
            :key="idx"
            :class="['message-item', msg.role === 'user' ? 'user-msg' : 'assistant-msg']"
          >
            <div class="msg-avatar">
              <el-avatar :size="36" :style="msg.role === 'user' ? 'background:#409eff' : 'background:#67c23a'">
                {{ msg.role === 'user' ? '我' : 'AI' }}
              </el-avatar>
            </div>
            <div class="msg-body">
              <!-- 多论文分析 AI 消息的关键词 -->
              <div v-if="msg.keywords && msg.keywords.length" class="keywords-row">
                <span class="kw-label">检索关键词：</span>
                <el-tag v-for="kw in msg.keywords" :key="kw" size="small" type="info" style="margin-right:4px">{{ kw }}</el-tag>
              </div>
              <div v-if="msg.role === 'assistant'" class="msg-content markdown-body" v-html="renderMarkdown(msg.content)" />
              <div v-else class="msg-content">{{ msg.content }}</div>
              <div class="msg-time">{{ formatTime(msg.timestamp) }}</div>
            </div>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Edit, Loading, Download } from '@element-plus/icons-vue'
import api from '../api/index.js'
import { renderMarkdown } from '../utils/markdown.js'
import { exportSessionAsMarkdown } from '../utils/export.js'

const route = useRoute()
const router = useRouter()
const session = ref({ title: '', messages: [], paper_ids: [], session_type: 'single' })
const loading = ref(false)
const messagesRef = ref(null)
const editingTitle = ref(false)
const editTitle = ref('')

// 是否可以继续对话（需要有 paper_ids）
const canContinue = computed(() => {
  return session.value.paper_ids && session.value.paper_ids.length > 0
})

onMounted(async () => {
  loading.value = true
  try {
    const res = await api.getSession(route.params.id)
    session.value = res.data
    await nextTick()
    scrollToBottom()
  } catch {
    ElMessage.error('获取会话详情失败')
  } finally {
    loading.value = false
  }
})

function scrollToBottom() {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

function startEditTitle() {
  editTitle.value = session.value.title
  editingTitle.value = true
}

async function saveTitle() {
  editingTitle.value = false
  const newTitle = editTitle.value.trim()
  if (!newTitle || newTitle === session.value.title) return
  try {
    await api.updateSession(route.params.id, { title: newTitle })
    session.value.title = newTitle
    ElMessage.success('标题已更新')
  } catch {
    ElMessage.error('更新标题失败')
  }
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function handleExport() {
  exportSessionAsMarkdown(session.value)
}

function continueSession() {
  const s = session.value
  if (!s.paper_ids || s.paper_ids.length === 0) return

  if (s.session_type === 'multi' && s.paper_ids.length >= 2) {
    router.push(`/?session_id=${s.id}&multi=true&paper_ids=${s.paper_ids.join(',')}`)
  } else {
    router.push(`/?session_id=${s.id}&paper_id=${s.paper_ids[0]}`)
  }
}
</script>

<style scoped>
.session-detail-wrap {
  min-height: 100vh;
  background: #f5f7fa;
  padding: 24px;
}

.session-detail-container {
  max-width: 860px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.page-header .title-area {
  flex: 1;
}

.title-area {
  display: flex;
  align-items: center;
  gap: 6px;
}

.title-area h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.loading-box {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.chat-card {
  min-height: 400px;
}

.paper-tags-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  padding: 8px 0 12px;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 12px;
}

.bar-label {
  font-size: 13px;
  color: #606266;
  flex-shrink: 0;
}

.keywords-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-bottom: 6px;
}

.kw-label {
  font-size: 12px;
  color: #909399;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-height: 70vh;
  overflow-y: auto;
  padding: 8px 0;
}

.message-item {
  display: flex;
  gap: 12px;
}

.user-msg {
  flex-direction: row-reverse;
}

.msg-body {
  max-width: 70%;
}

.user-msg .msg-body {
  align-items: flex-end;
  display: flex;
  flex-direction: column;
}

.msg-content {
  background: #f0f2f5;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.user-msg .msg-content {
  background: #ecf5ff;
  color: #303133;
}

.msg-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
}
</style>
