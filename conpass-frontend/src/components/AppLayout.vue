<template>
  <div class="layout">
    <!-- サイドバー -->
    <aside class="sidebar">
      <div class="sidebar-logo">ConPass</div>
      <nav class="sidebar-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          custom
          v-slot="{ isActive, navigate }"
        >
          <div class="nav-item" :class="{ active: isActive }" @click="navigate">
            <span>{{ item.icon }}</span>
            <span>{{ item.label }}</span>
          </div>
        </RouterLink>
      </nav>
      <div class="sidebar-user" v-if="auth.user">
        {{ auth.user.accountName }}<br />
        {{ auth.user.loginName }}
      </div>
    </aside>

    <!-- メインエリア -->
    <div class="main">
      <header class="topbar">
        <span class="topbar-title">{{ pageTitle }}</span>
        <button class="btn btn-ghost" @click="handleLogout">ログアウト</button>
      </header>
      <main class="page">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, useRouter, useRoute } from 'vue-router'
import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const navItems = [
  { to: '/dashboard',     label: 'ダッシュボード', icon: '📊' },
  { to: '/contracts',     label: '契約書一覧',     icon: '📄' },
  { to: '/playbooks',     label: 'Playbook',       icon: '📋' },
  { to: '/settings/laws', label: '法令管理',        icon: '⚖️' },
]

const titleMap: Record<string, string> = {
  '/dashboard':     'ダッシュボード',
  '/contracts':     '契約書一覧',
  '/playbooks':     'Playbook 管理',
  '/settings/laws': '法令・規制管理',
}
const pageTitle = computed(() => titleMap[route.path] ?? '')

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>
