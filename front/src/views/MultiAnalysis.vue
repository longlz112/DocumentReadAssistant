<template>
  <div class="multi-analysis">
    <!-- 已选论文标签 -->
    <div class="selected-papers">
      <span class="label">已选论文：</span>
      <el-tag
          v-for="paper in selectedPapers"
          :key="paper.id"
          closable
          @close="$emit('remove-paper', paper)"
          class="paper-tag"
      >
        {{ paper.title }}
      </el-tag>
    </div>

    <!-- 对话区 -->
    <div class="chat-box" ref="chatBox">
      <div v-for="(msg, index) in chatHistory" :key="index" :class="['message', msg.role]">
        <div class="msg-bubble">
          <template v-if="msg.role === 'ai' && msg.keywords && msg.keywords.length">
            <div class="keywords-row">
              <span class="kw-label">检索关键词：</span>
              <el-tag v-for="kw in msg.keywords" :key="kw" size="small" type="info" class="kw-tag">{{ kw }}</el-tag>
            </div>
            <div class="divider"></div>
          </template>
          <div v-if="msg.role === 'ai'" class="markdown-body" v-html="renderMarkdown(msg.content)" />
          <template v-else>{{ msg.content }}</template>
        </div>
      </div>
      <div v-if="analyzing" class="message ai">
        <div class="msg-bubble loading">AI 正在分析多篇论文，请稍候...</div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <el-input
          v-model="question"
          type="textarea"
          :rows="3"
          placeholder="提问关于这些论文的对比问题，例如：这几篇论文在 RAG 技术上有哪些相似点？"
          @keyup.enter.ctrl="sendQuestion"
      />
      <el-button
          type="primary"
          class="send-btn"
          @click="sendQuestion"
          :loading="analyzing"
          :disabled="selectedPapers.length < 2"
      >
        发送 (Ctrl+Enter)
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { renderMarkdown } from '../utils/markdown.js'

const props = defineProps({
  selectedPapers: {
    type: Array,
    default: () => [],
  },
})
defineEmits(['remove-paper'])

const chatBox = ref(null)
const question = ref('')
const analyzing = ref(false)
const chatHistory = ref([])
let currentSessionId = null  // 当前多论文分析会话 _id

// 论文列表变化时重置会话（新的论文组合 = 新会话）
watch(
    () => props.selectedPapers.map(p => p.id).join(','),
    () => {
      currentSessionId = null
      if (props.selectedPapers.length >= 2) {
        chatHistory.value.push({
          role: 'ai',
          content: `已选中 ${props.selectedPapers.length} 篇论文，可以开始提问了。`,
          keywords: [],
        })
        scrollToBottom()
      }
    }
)

const scrollToBottom = async () => {
  await nextTick()
  if (chatBox.value) {
    chatBox.value.scrollTop = chatBox.value.scrollHeight
  }
}

const sendQuestion = async () => {
  if (!question.value.trim()) return
  if (props.selectedPapers.length < 2) {
    return ElMessage.warning('请至少选择两篇论文')
  }
  const notReady = props.selectedPapers.filter(p => !p.is_processed)
  if (notReady.length) {
    return ElMessage.warning(`以下论文尚未解析完成：${notReady.map(p => p.title).join('、')}`)
  }

  const qText = question.value
  chatHistory.value.push({ role: 'user', content: qText })
  question.value = ''
  analyzing.value = true
  scrollToBottom()

  // 首次提问时创建多论文分析会话
  if (!currentSessionId) {
    try {
      const titles = props.selectedPapers.map(p => p.title)
      const sessionTitle = `多论文分析：${titles.slice(0, 2).join('、')}${titles.length > 2 ? '等' : ''}`
      const sessionRes = await api.createSession({
        title: sessionTitle,
        session_type: 'multi',
        paper_titles: titles,
      })
      currentSessionId = sessionRes.data.id
    } catch {
      // 会话创建失败不阻断问答
    }
  }

  // 保存用户消息
  if (currentSessionId) {
    api.addMessage(currentSessionId, 'user', qText).catch(() => {})
  }

  try {
    const ids = props.selectedPapers.map(p => p.id)
    const res = await api.analyzeMultiple(ids, qText)
    const answer = res.data.answer
    const keywords = res.data.keywords || []
    chatHistory.value.push({ role: 'ai', content: answer, keywords })

    // 保存 AI 回复（含关键词）
    if (currentSessionId) {
      api.addMessage(currentSessionId, 'assistant', answer, keywords).catch(() => {})
    }
  } catch (error) {
    chatHistory.value.push({ role: 'ai', content: '抱歉，请求失败，请检查系统日志。', keywords: [] })
  } finally {
    analyzing.value = false
    scrollToBottom()
  }
}
</script>

<style scoped>
.multi-analysis {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.selected-papers {
  padding: 10px 15px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-height: 46px;
  background: #f5f7fa;
}
.label { font-size: 13px; color: #606266; flex-shrink: 0; }
.paper-tag { max-width: 180px; overflow: hidden; text-overflow: ellipsis; }

.chat-box {
  flex-grow: 1;
  padding: 15px;
  overflow-y: auto;
  background-color: #fafafa;
}
.message { margin-bottom: 15px; display: flex; }
.message.user { justify-content: flex-end; }
.message.ai { justify-content: flex-start; }
.msg-bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 8px;
  line-height: 1.6;
  white-space: pre-wrap;
  font-size: 14px;
}
.user .msg-bubble { background-color: #95ec69; color: #000; }
.ai .msg-bubble { background-color: #fff; border: 1px solid #ebeef5; color: #333; }
.loading { color: #909399; font-style: italic; }

.keywords-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  margin-bottom: 8px;
}
.kw-label { font-size: 12px; color: #909399; }
.kw-tag { font-size: 12px; }
.divider { border-top: 1px solid #ebeef5; margin-bottom: 8px; }

.input-area {
  padding: 15px;
  border-top: 1px solid #ebeef5;
  background: #fff;
}
.send-btn { margin-top: 10px; width: 100%; }
</style>
