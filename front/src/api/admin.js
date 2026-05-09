import axios from 'axios'

const adminApi = axios.create({
    baseURL: 'http://localhost:8000/admin-api/',
    timeout: 30000,
})

adminApi.interceptors.request.use(config => {
    const token = localStorage.getItem('admin_token')
    if (token) {
        config.headers.Authorization = `Token ${token}`
    }
    return config
})

export default {
    login: (data) => adminApi.post('auth/login/', data),
    getStats: () => adminApi.get('stats/'),
    getUsers: (params) => adminApi.get('users/', { params }),
    updateUser: (id, data) => adminApi.put(`users/${id}/`, data),
    getPapers: (params) => adminApi.get('papers/', { params }),
    batchUpdatePapers: (data) => adminApi.patch('papers/', data),
    getKeywords: () => adminApi.get('papers/keywords/'),
    getSystem: () => adminApi.get('system/'),
    getLLMStats: () => adminApi.get('llm/stats/'),
    getLLMRecords: (params) => adminApi.get('llm/records/', { params }),
}
