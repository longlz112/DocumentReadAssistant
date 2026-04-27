import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import UserCenter from '../views/UserCenter.vue'
import SessionList from '../views/SessionList.vue'
import SessionDetail from '../views/SessionDetail.vue'

const routes = [
    { path: '/login', component: Login },
    { path: '/', component: Dashboard, meta: { requiresAuth: true } },
    { path: '/user-center', component: UserCenter, meta: { requiresAuth: true } },
    { path: '/sessions', component: SessionList, meta: { requiresAuth: true } },
    { path: '/sessions/:id', component: SessionDetail, meta: { requiresAuth: true } },
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

// 路由守卫拦截
router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('token')
    if (to.meta.requiresAuth && !token) {
        next('/login')
    } else {
        next()
    }
})

export default router
