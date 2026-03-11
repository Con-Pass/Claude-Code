import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('../views/DashboardView.vue') },
  { path: '/contracts', name: 'Contracts', component: () => import('../views/ContractListView.vue') },
  { path: '/contracts/:id', name: 'ContractDetail', component: () => import('../views/ContractDetailView.vue') },
  { path: '/playbooks', name: 'Playbooks', component: () => import('../views/PlaybookView.vue') },
  { path: '/settings/laws', name: 'Laws', component: () => import('../views/LawsView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    await auth.fetchUser()
    if (!auth.isLoggedIn) return '/login'
  }
})

export default router
