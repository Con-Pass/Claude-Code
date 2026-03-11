import Vue from 'vue'
import VueRouter from 'vue-router'

Vue.use(VueRouter)

const routes = [
  // デフォルト: ダッシュボードへリダイレクト
  {
    path: '/',
    redirect: '/dashboard'
  },

  // FE1: ダッシュボード・Playbookエディタ・ルール管理
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import(/* webpackChunkName: "dashboard" */ '../views/Dashboard.vue'),
    meta: { title: 'ダッシュボード', role: 'sme' }
  },
  {
    path: '/advisor',
    name: 'AdvisorDashboard',
    component: () => import(/* webpackChunkName: "advisor" */ '../views/AdvisorDashboard.vue'),
    meta: { title: '士業ダッシュボード', role: 'advisor' }
  },
  {
    path: '/playbook',
    name: 'PlaybookEditor',
    component: () => import(/* webpackChunkName: "playbook" */ '../views/PlaybookEditor.vue'),
    meta: { title: 'Playbookエディタ', role: 'sme' }
  },
  {
    path: '/rules',
    name: 'RuleManager',
    component: () => import(/* webpackChunkName: "rules" */ '../views/RuleManager.vue'),
    meta: { title: 'ルール管理', role: 'sme' }
  },

  // FE2: STプラン訴求・コンプライアンス・テンプレート比較・OEM
  {
    path: '/plan/compare',
    name: 'PlanCompare',
    component: () => import(/* webpackChunkName: "plan" */ '../views/PlanCompare.vue'),
    meta: { title: 'プラン比較' }
  },
  {
    path: '/onboarding',
    name: 'Onboarding',
    component: () => import(/* webpackChunkName: "onboarding" */ '../views/Onboarding.vue'),
    meta: { title: 'はじめに' }
  },
  {
    path: '/compliance',
    name: 'ComplianceDashboard',
    component: () => import(/* webpackChunkName: "compliance" */ '../views/ComplianceDashboard.vue'),
    meta: { title: 'コンプライアンス', role: 'sme' }
  },
  {
    path: '/template/compare',
    name: 'TemplateCompare',
    component: () => import(/* webpackChunkName: "template" */ '../views/TemplateCompare.vue'),
    meta: { title: 'テンプレート比較' }
  },
  {
    path: '/oem',
    name: 'OEMDashboard',
    component: () => import(/* webpackChunkName: "oem" */ '../views/OEMDashboard.vue'),
    meta: { title: 'OEMダッシュボード', role: 'admin' }
  },

  // 404 フォールバック
  {
    path: '*',
    redirect: '/dashboard'
  }
]

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    return { x: 0, y: 0 }
  }
})

// ページタイトル更新
router.afterEach((to) => {
  if (to.meta && to.meta.title) {
    document.title = to.meta.title + ' - ConPass'
  }
})

export default router
