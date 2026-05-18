<template>
  <div class="workspace">
    <!-- 左侧：PDF预览 / 知识图谱 -->
    <div class="left-panel">
      <div class="tab-bar">
        <span :class="['tab', { active: activeTab === 'pdf' }]" @click="activeTab = 'pdf'">PDF 预览</span>
        <span :class="['tab', { active: activeTab === 'graph' }]" @click="switchToGraph">知识图谱</span>
      </div>

      <div v-show="activeTab === 'pdf'" class="tab-content">
        <iframe :src="paper.file" class="pdf-iframe"></iframe>
      </div>

      <div v-show="activeTab === 'graph'" class="tab-content graph-panel">
        <div v-if="graphStatus === '' || graphStatus === 'error'" class="graph-placeholder">
          <p v-if="graphStatus === 'error'" class="error-text">知识图谱构建失败，请重试</p>
          <p v-else class="hint-text">尚未构建知识图谱</p>
          <el-button type="primary" :loading="graphBuilding" @click="triggerBuildGraph">
            {{ graphStatus === 'error' ? '重新构建' : '构建知识图谱' }}
          </el-button>
        </div>

        <div v-else-if="graphStatus === 'building'" class="graph-placeholder">
          <el-icon class="spinning"><Loading /></el-icon>
          <p class="hint-text">知识图谱构建中，请稍候...</p>
        </div>

        <div v-else-if="graphStatus === 'ready'" class="chart-wrapper">
          <div ref="chartDom" class="echarts-container"></div>
        </div>
      </div>
    </div>

    <!-- 右侧问答区 -->
    <div class="interaction-container">
      <div class="qa-header">AI 问答</div>
      <div class="chat-box" ref="chatBox">
        <div v-for="(msg, index) in chatHistory" :key="index" :class="['message', msg.role]">
          <div v-if="msg.role === 'ai'" class="msg-bubble markdown-body" v-html="renderMarkdown(msg.content)" />
          <div v-else class="msg-bubble">{{ msg.content }}</div>
        </div>
        <div v-if="asking && !streamingActive" class="message ai">
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
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import api from '../api'
import { renderMarkdown } from '../utils/markdown.js'

const props = defineProps({
  paper: Object,
  initialSessionId: { type: String, default: null },
})

// ── QA ─────────────────────────────────────────────
const chatBox = ref(null)
const question = ref('')
const asking = ref(false)
const streamingActive = ref(false)
const chatHistory = ref([])
let currentSessionId = null

// 论文切换时重置
watch(() => props.paper?.id, () => {
  chatHistory.value = []
  currentSessionId = null
  graphStatus.value = props.paper?.knowledge_graph_status || ''
  activeTab.value = 'pdf'
  stopPolling()
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

// 加载已有会话历史（继续对话）
onMounted(async () => {
  if (props.initialSessionId) {
    try {
      const res = await api.getSession(props.initialSessionId)
      const msgs = res.data.messages || []
      chatHistory.value = msgs.map(m => ({
        role: m.role === 'assistant' ? 'ai' : 'user',
        content: m.content,
      }))
      currentSessionId = props.initialSessionId
      await nextTick()
      scrollToBottom()
    } catch {
      // 静默失败，不影响正常使用
    }
  }
})

const scrollToBottom = async () => {
  await nextTick()
  if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
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

  // 首次提问时创建会话
  if (!currentSessionId) {
    try {
      const sessionRes = await api.createSession({
        title: props.paper.title || '新会话',
        session_type: 'single',
        paper_ids: [props.paper.id],
        paper_titles: [props.paper.title],
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

  // 添加 AI 消息占位
  chatHistory.value.push({ role: 'ai', content: '' })
  const aiMsg = chatHistory.value[chatHistory.value.length - 1]
  let fullAnswer = ''

  try {
    const response = await api.askStream(props.paper.id, qText, currentSessionId)

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    streamingActive.value = true
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()  // 保留未完整的行

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (raw === '[DONE]') continue
        try {
          const parsed = JSON.parse(raw)
          if (parsed.content) {
            fullAnswer += parsed.content
            aiMsg.content = fullAnswer
            scrollToBottom()
          }
        } catch {
          // 忽略解析错误
        }
      }
    }

    if (!fullAnswer) {
      aiMsg.content = '抱歉，未收到回复。'
    }

    // 保存 AI 回复
    if (currentSessionId && fullAnswer) {
      api.addMessage(currentSessionId, 'assistant', fullAnswer).catch(() => {})
    }
  } catch {
    aiMsg.content = '抱歉，请求失败，请检查系统日志。'
  } finally {
    asking.value = false
    streamingActive.value = false
    scrollToBottom()
  }
}

// ── 知识图谱 ────────────────────────────────────────
const activeTab = ref('pdf')
const graphStatus = ref(props.paper?.knowledge_graph_status || '')
const graphBuilding = ref(false)
const chartDom = ref(null)
let chartInstance = null
let pollTimer = null

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const renderGraph = (graphData) => {
  nextTick(() => {
    if (!chartDom.value) return
    if (chartInstance) chartInstance.dispose()
    chartInstance = echarts.init(chartDom.value)

    const catNames = graphData.categories.map(c => c.name)
    const nodes = graphData.nodes.map(n => ({
      ...n,
      category: catNames.indexOf(n.category),
    }))

    const option = {
      tooltip: {
        formatter: (params) => {
          if (params.dataType === 'node') return params.data.name
          return `${params.data.source} → ${params.data.target}<br/>${params.data.value}`
        },
      },
      legend: { data: catNames, top: 8, textStyle: { fontSize: 12 } },
      toolbox: {
        show: true,
        top: 'center',
        feature: {
          saveAsImage: { show: true, type: 'png', name: '图表名称', backgroundColor: '#fff', pixelRatio: 2 }
        }
      },
      series: [{
        type: 'graph',
        layout: 'force',
        data: nodes,
        links: graphData.links,
        categories: graphData.categories,
        roam: true,
        draggable: true,
        label: { show: true, position: 'right', fontSize: 11 },
        edgeLabel: { show: true, formatter: (params) => params.data.value, fontSize: 10, color: '#666' },
        force: { repulsion: 200, gravity: 0.05, edgeLength: [80, 200] },
        lineStyle: { color: 'source', curveness: 0.2, opacity: 0.7 },
        emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
      }],
    }
    chartInstance.setOption(option)

    const resizeObserver = new ResizeObserver(() => chartInstance && chartInstance.resize())
    resizeObserver.observe(chartDom.value)
  })
}

const fetchAndRenderGraph = async () => {
  try {
    const res = await api.getKnowledgeGraph(props.paper.id)
    graphStatus.value = res.data.status
    if (res.data.status === 'ready' && res.data.data) {
      stopPolling()
      renderGraph(res.data.data)
    } else if (res.data.status === 'error') {
      stopPolling()
    }
  } catch {
    // 网络错误时静默处理
  }
}

const switchToGraph = async () => {
  activeTab.value = 'graph'
  if (graphStatus.value === 'ready' && !chartInstance) {
    const res = await api.getKnowledgeGraph(props.paper.id)
    if (res.data.data) renderGraph(res.data.data)
  } else if (graphStatus.value === 'building') {
    startPolling()
  }
}

const startPolling = () => {
  if (pollTimer) return
  pollTimer = setInterval(fetchAndRenderGraph, 2000)
}

const triggerBuildGraph = async () => {
  if (!props.paper.is_processed) {
    return ElMessage.warning('论文尚未解析完成')
  }
  graphBuilding.value = true
  try {
    await api.buildKnowledgeGraph(props.paper.id)
    graphStatus.value = 'building'
    startPolling()
  } catch (err) {
    ElMessage.error(err.response?.data?.error || '构建请求失败')
  } finally {
    graphBuilding.value = false
  }
}

onUnmounted(() => {
  stopPolling()
  if (chartInstance) chartInstance.dispose()
})
</script>

<style scoped>
.workspace { display: flex; height: 100%; }

.left-panel {
  flex: 6;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #dcdfe6;
  overflow: hidden;
}

.tab-bar { display: flex; border-bottom: 1px solid #dcdfe6; background: #f5f7fa; flex-shrink: 0; }
.tab {
  padding: 10px 20px;
  font-size: 13px;
  cursor: pointer;
  color: #606266;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}
.tab:hover { color: #409eff; }
.tab.active { color: #409eff; border-bottom-color: #409eff; font-weight: 600; background: #fff; }

.tab-content { flex: 1; overflow: hidden; }
.pdf-iframe { width: 100%; height: 100%; border: none; }

.graph-panel { display: flex; align-items: center; justify-content: center; background: #fafafa; }
.graph-placeholder { text-align: center; }
.hint-text { color: #909399; margin-bottom: 16px; }
.error-text { color: #f56c6c; margin-bottom: 8px; }
.spinning { font-size: 32px; color: #409eff; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.chart-wrapper { width: 100%; height: 100%; position: relative; }
.echarts-container { width: 100%; height: 100%; }

.interaction-container { flex: 4; display: flex; flex-direction: column; background-color: #fff; }
.qa-header { padding: 12px 16px; font-size: 14px; font-weight: 600; border-bottom: 1px solid #ebeef5; color: #303133; }
.chat-box { flex-grow: 1; padding: 15px; overflow-y: auto; background-color: #fafafa; }
.message { margin-bottom: 15px; display: flex; }
.message.user { justify-content: flex-end; }
.message.ai { justify-content: flex-start; }
.msg-bubble { max-width: 80%; padding: 10px 14px; border-radius: 8px; line-height: 1.5; font-size: 14px; }
.user .msg-bubble { background-color: #95ec69; color: #000; }
.ai .msg-bubble { background-color: #fff; border: 1px solid #ebeef5; color: #333; }
.loading { color: #909399; font-style: italic; }
.input-area { padding: 15px; border-top: 1px solid #ebeef5; background: #fff; }
.send-btn { margin-top: 10px; width: 100%; }
</style>
