import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<{ id: number; loginName: string; accountName: string } | null>(null)
  const isLoggedIn = ref(false)

  async function login(loginName: string, password: string) {
    const res = await api.post('/auth/login', { login_name: loginName, password })
    // JWT は HttpOnly Cookie に自動でセットされる
    await fetchUser()
    return res
  }

  async function fetchUser() {
    try {
      const res = await api.get('/user')
      const d = res.data
      user.value = {
        id: d.id,
        loginName: d.loginName ?? d.login_name,
        accountName: d.account?.name ?? '',
      }
      isLoggedIn.value = true
    } catch {
      user.value = null
      isLoggedIn.value = false
    }
  }

  async function logout() {
    await api.post('/auth/logout').catch(() => {})
    user.value = null
    isLoggedIn.value = false
  }

  return { user, isLoggedIn, login, fetchUser, logout }
})
