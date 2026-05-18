import axios from 'axios'

const BASE_URL = 'http://localhost:8000/api/'

const api = axios.create({
    baseURL: BASE_URL,
    timeout: 60000,
})

// 请求拦截器：自动带上 Token
api.interceptors.request.use(config => {
    const token = localStorage.getItem('token')
    if (token) {
        config.headers.Authorization = `Token ${token}`
    }
    return config
})

// 流式请求辅助函数（使用原生 fetch，以支持 ReadableStream）
function _streamFetch(path, body) {
    const token = localStorage.getItem('token')
    return fetch(BASE_URL + path, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Token ${token}` } : {}),
        },
        body: JSON.stringify(body),
    })
}

export default {
    // 认证
    login: (data) => api.post('auth/', { ...data, action: 'login' }),
    register: (data) => api.post('auth/', { ...data, action: 'register' }),

    // 论文
    getPapers: () => api.get('papers/'),
    uploadPaper: (formData) => api.post('papers/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    }),
    deletePaper: (paperId) => api.delete(`papers/${paperId}/`),
    askQuestion: (paperId, question, sessionId = null) =>
        api.post(`papers/${paperId}/ask/`, { question, session_id: sessionId }),
    askStream: (paperId, question, sessionId = null) =>
        _streamFetch(`papers/${paperId}/ask_stream/`, { question, session_id: sessionId }),
    pollingStatus: (paperId) => api.get(`papers/${paperId}/status/`),
    reparsePaper: (paperId) => api.post(`papers/${paperId}/reparse/`),
    analyzeMultiple: (paperIds, question, sessionId = null) =>
        api.post('papers/analyze_multi/', { paper_ids: paperIds, question, session_id: sessionId }),
    analyzeMultipleStream: (paperIds, question, sessionId = null) =>
        _streamFetch('papers/analyze_multi_stream/', { paper_ids: paperIds, question, session_id: sessionId }),

    // 元数据
    getMetadata: (paperId) => api.get(`papers/${paperId}/metadata/`),
    reextractMetadata: (paperId) => api.post(`papers/${paperId}/reextract_metadata/`),
    updateMetadata: (paperId, data) => api.post(`papers/${paperId}/update_metadata/`, data),

    // 知识图谱
    buildKnowledgeGraph: (paperId) => api.post(`papers/${paperId}/build_knowledge_graph/`),
    getKnowledgeGraph: (paperId) => api.get(`papers/${paperId}/knowledge_graph/`),

    // 用户个人信息
    getUserProfile: () => api.get('user/profile/'),
    updateUserProfile: (data) => api.put('user/profile/', data),

    // 会话记录
    getSessions: (page = 1, pageSize = 10) => api.get('sessions/', { params: { page, page_size: pageSize } }),
    getSession: (id) => api.get(`sessions/${id}/`),
    createSession: (data) => api.post('sessions/', data),
    updateSession: (id, data) => api.patch(`sessions/${id}/`, data),
    deleteSession: (id) => api.delete(`sessions/${id}/`),
    addMessage: (id, role, content, keywords) =>
        api.post(`sessions/${id}/add_message/`, { role, content, ...(keywords ? { keywords } : {}) }),
}
