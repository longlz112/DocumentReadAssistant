<template>
  <div class="workspace">
    <!-- 左侧 PDF 预览 -->
    <div class="pdf-container">
      <iframe :src="paper.file" class="pdf-iframe"></iframe>
    </div>

    <!-- 右侧交互区（问答 & 笔记） -->
    <div class="interaction-container">
      <el-tabs v-model="activeTab" class="custom-tabs">
        <!-- AI 问答 Tab -->
        <el-tab-pane label="AI 问答" name="qa" class="tab-content">
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
        </el-tab-pane>


      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const props = defineProps({
  paper: Object,
})


const activeTab = ref('qa')
const chatBox = ref(null)

// 问答相关
const question = ref('')
const asking = ref(false)
const chatHistory = ref([])

// 笔记相关
const notes = ref([])
const newNote = ref('')


// 当切换论文时，重置状态并拉取新笔记
watch(() => props.paper.id, () => {
  chatHistory.value = []
  fetchNotes()
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

const fetchNotes = async () => {
  try {
    const res = await api.getNotes(props.paper.id)
    notes.value = res.data
  } catch (error) {
    console.error('获取笔记失败')
  }
}

const addNote = async () => {
  if (!newNote.value.trim()) return
  try {
    await api.addNote(props.paper.id, newNote.value)
    ElMessage.success('笔记已保存')
    newNote.value = ''
    fetchNotes()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const deleteNote = async (noteId) => {
  try {
    await api.deleteNote(noteId)
    ElMessage.success('已删除')
    fetchNotes()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  fetchNotes()
})
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
.custom-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}
:deep(.el-tabs__content) {
  flex-grow: 1;
  padding: 0;
}
.tab-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* 聊天区样式 */
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

/* 笔记区样式 */
.notes-list {
  flex-grow: 1;
  padding: 15px;
  overflow-y: auto;
  background-color: #fafafa;
}
.note-card { margin-bottom: 10px; }
.note-content { font-size: 14px; white-space: pre-wrap; margin-bottom: 10px; }
.note-actions { display: flex; justify-content: space-between; align-items: center; }
.note-time { font-size: 12px; color: #909399; }

/* 底部输入区 */
.input-area {
  padding: 15px;
  border-top: 1px solid #ebeef5;
  background: #fff;
}
.send-btn { margin-top: 10px; width: 100%; }
</style>
