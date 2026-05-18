import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import UserCenter from '../views/UserCenter.vue'
import SessionList from '../views/SessionList.vue'
import SessionDetail from '../views/SessionDetail.vue'
import AdminLogin from '../views/admin/AdminLogin.vue'
import AdminLayout from '../views/admin/AdminLayout.vue'
import AdminDashboard from '../views/admin/AdminDashboard.vue'
import AdminUsers from '../views/admin/AdminUsers.vue'
import AdminPapers from '../views/admin/AdminPapers.vue'
import AdminMonitor from '../views/admin/AdminMonitor.vue'
import AdminLLM from '../views/admin/AdminLLM.vue'
import AdminLogs from '../views/admin/AdminLogs.vue'

const routes = [
    { path: '/login', component: Login },
    { path: '/', component: Dashboard, meta: { requiresAuth: true } },
    { path: '/user-center', component: UserCenter, meta: { requiresAuth: true } },
    { path: '/sessions', component: SessionList, meta: { requiresAuth: true } },
    { path: '/sessions/:id', component: SessionDetail, meta: { requiresAuth: true } },
    { path: '/admin/login', component: AdminLogin },
    {
        path: '/admin',
        component: AdminLayout,
        meta: { requiresAdmin: true },
        children: [
            { path: '', redirect: '/admin/dashboard' },
            { path: 'dashboard', component: AdminDashboard },
            { path: 'users', component: AdminUsers },
            { path: 'papers', component: AdminPapers },
            { path: 'monitor', component: AdminMonitor },
            { path: 'llm', component: AdminLLM },
            { path: 'logs', component: AdminLogs },
        ],
    },
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

router.beforeEach((to, from, next) => {
    if (to.meta.requiresAuth && !localStorage.getItem('token')) {
        next('/login')
    } else if (to.meta.requiresAdmin && !localStorage.getItem('admin_token')) {
        next('/admin/login')
    } else {
        next()
    }
})

export default router
