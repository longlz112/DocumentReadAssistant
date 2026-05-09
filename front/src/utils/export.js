/**
 * 触发浏览器下载文本文件
 */
function downloadText(content, filename) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * 将会话数据转换为 Markdown 字符串
 */
export function sessionToMarkdown(session) {
  const lines = []
  const typeLabel = session.session_type === 'multi' ? '多论文分析' : '单论文问答'
  const createdAt = session.created_at
    ? new Date(session.created_at).toLocaleString('zh-CN')
    : ''

  lines.push(`# ${session.title}`)
  lines.push('')
  lines.push(`**会话类型：** ${typeLabel}`)
  if (createdAt) lines.push(`**创建时间：** ${createdAt}`)
  if (session.session_type === 'multi' && session.paper_titles?.length) {
    lines.push(`**分析论文：** ${session.paper_titles.join('、')}`)
  }
  lines.push('')
  lines.push('---')
  lines.push('')

  const messages = session.messages || []
  if (messages.length === 0) {
    lines.push('*该会话暂无消息记录*')
  } else {
    messages.forEach((msg) => {
      const time = msg.timestamp
        ? new Date(msg.timestamp).toLocaleString('zh-CN')
        : ''
      if (msg.role === 'user') {
        lines.push(`### 提问${time ? `（${time}）` : ''}`)
        lines.push('')
        lines.push(msg.content)
      } else {
        lines.push(`### AI 回答${time ? `（${time}）` : ''}`)
        if (msg.keywords?.length) {
          lines.push('')
          lines.push(`> 检索关键词：${msg.keywords.join('、')}`)
        }
        lines.push('')
        lines.push(msg.content)
      }
      lines.push('')
      lines.push('---')
      lines.push('')
    })
  }

  return lines.join('\n')
}

/**
 * 导出会话为 Markdown 文件
 */
export function exportSessionAsMarkdown(session) {
  const md = sessionToMarkdown(session)
  const safeName = (session.title || '会话').replace(/[\\/:*?"<>|]/g, '_')
  downloadText(md, `${safeName}.md`)
}
