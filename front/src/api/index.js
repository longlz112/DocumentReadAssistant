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
    analyzeMultiple: (paperIds, question) => api.post('papers/analyze_multi/', { paper_ids: paperIds, question }),

    // 元数据
    getMetadata: (paperId) => api.get(`papers/${paperId}/metadata/`),
    reextractMetadata: (paperId) => api.post(`papers/${paperId}/reextract_metadata/`),
    updateMetadata: (paperId, data) => api.post(`papers/${paperId}/update_metadata/`, data),
}
