<template>
  <div class="workspace">
    <!-- 左侧 PDF 预览 -->
    <div class="pdf-container">
      <iframe :src="paper.file" class="pdf-iframe"></iframe>
    </div>

    <!-- 右侧问答区 -->
    <div class="interaction-container">
      <div class="qa-header">AI 问答</div>
      <div class="chat-box" ref="chatBox">
        <div v-for="(msg, index) in chatHistory" :key="index" :class="['message', msg.role]">
          <div class="msg-bubble">{{ msg.content }}</div>
        </div>
        <div v-if="asking" class="message ai">
          <div class="msg-bubble loading">AI思考中...</div>
        </div>
      </div>
      <div class="input-area">
        <el-input
            v-model="question"
            type="textarea"
            :rows="3"
            placeholder="向大模型提问关于这篇论文的内容..."
            @keyup.enter.ctrl="askQuestion"
        />
        <el-button type="primary" class="send-btn" @click="askQuestion" :loading="asking">
          发送 (Ctrl+Enter)
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const props = defineProps({
  paper: Object,
})

const chatBox = ref(null)
const question = ref('')
const asking = ref(false)
const chatHistory = ref([])

watch(() => props.paper.id, () => {
  chatHistory.value = []
})

const scrollToBottom = async () => {
  await nextTick()
  if (chatBox.value) {
    chatBox.value.scrollTop = chatBox.value.scrollHeight
  }
}

const askQuestion = async () => {
  if (!question.value.trim()) return
  if (!props.paper.is_processed) {
    return ElMessage.warning('论文仍在解析中，请稍后再试')
  }

  const qText = question.value
  chatHistory.value.push({ role: 'user', content: qText })
  question.value = ''
  asking.value = true
  scrollToBottom()

  try {
    const res = await api.askQuestion(props.paper.id, qText)
    chatHistory.value.push({ role: 'ai', content: res.data.answer })
  } catch (error) {
    chatHistory.value.push({ role: 'ai', content: '抱歉，请求失败，请检查系统日志。' })
  } finally {
    asking.value = false
    scrollToBottom()
  }
}
</script>

<style scoped>
.workspace {
  display: flex;
  height: 100%;
}
.pdf-container {
  flex: 6;
  border-right: 1px solid #dcdfe6;
}
.pdf-iframe {
  width: 100%;
  height: 100%;
  border: none;
}
.interaction-container {
  flex: 4;
  display: flex;
  flex-direction: column;
  background-color: #fff;
}
.qa-header {
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  border-bottom: 1px solid #ebeef5;
  color: #303133;
}
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
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 8px;
  line-height: 1.5;
  white-space: pre-wrap;
  font-size: 14px;
}
.user .msg-bubble { background-color: #95ec69; color: #000; }
.ai .msg-bubble { background-color: #fff; border: 1px solid #ebeef5; color: #333; }
.loading { color: #909399; font-style: italic; }
.input-area {
  padding: 15px;
  border-top: 1px solid #ebeef5;
  background: #fff;
}
.send-btn { margin-top: 10px; width: 100%; }
</style>

