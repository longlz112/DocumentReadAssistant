import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 配置 marked：启用 GitHub Flavored Markdown
marked.setOptions({
  breaks: true,    // 单个换行符转为 <br>
  gfm: true,       // GitHub Flavored Markdown
})

/**
 * 将 Markdown 字符串渲染为经过净化的 HTML，可直接用于 v-html。
 */
export function renderMarkdown(text) {
  if (!text) return ''
  const rawHtml = marked.parse(text)
  return DOMPurify.sanitize(rawHtml)
}
