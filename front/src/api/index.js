import axios from 'axios'

const api = axios.create({
    baseURL: 'http://localhost:8000/api/', // Django 后端地址
    timeout: 60000, // 大模型回答较慢，超时设长一点
})

// 请求拦截器：自动带上 Token
api.interceptors.request.use(config => {
    const token = localStorage.getItem('token')
    if (token) {
        config.headers.Authorization = `Token ${token}`
    }
    return config
})

export default {
    // 认证
    login: (data) => api.post('auth/', { ...data, action: 'login' }),
    register: (data) => api.post('auth/', { ...data, action: 'register' }),

    // 论文
    getPapers: () => api.get('papers/'),
    uploadPaper: (formData) => api.post('papers/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    }),
    askQuestion: (paperId, question) => api.post(`papers/${paperId}/ask/`, { question }),
    pollingStatus: (paperId) => api.get(`papers/${paperId}/status/`),

    // 笔记
    getNotes: (paperId) => api.get(`notes/?paper_id=${paperId}`),
    addNote: (paperId, content) => api.post('notes/', { paper: paperId, content }),
    deleteNote: (noteId) => api.delete(`notes/${noteId}/`)
}
