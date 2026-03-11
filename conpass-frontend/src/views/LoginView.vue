<template>
  <div class="login-page">
    <div class="login-box">
      <div class="login-logo">
        <h1>ConPass</h1>
        <p>電子契約管理システム</p>
      </div>

      <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>

      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label class="form-label">メールアドレス（ログインID）</label>
          <input class="input" v-model="loginName" type="email" placeholder="example@company.com" autocomplete="username" required />
        </div>
        <div class="form-group">
          <label class="form-label">パスワード</label>
          <input class="input" v-model="password" type="password" autocomplete="current-password" required />
        </div>
        <button class="btn btn-primary" style="width:100%; justify-content:center;" :disabled="loading">
          {{ loading ? 'ログイン中...' : 'ログイン' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const loginName = ref('')
const password  = ref('')
const loading   = ref(false)
const errorMsg  = ref('')

async function handleLogin() {
  loading.value = true
  errorMsg.value = ''
  try {
    await auth.login(loginName.value, password.value)
    router.push('/dashboard')
  } catch (e: any) {
    const data = e?.response?.data
    errorMsg.value = data?.error_message ?? data?.nonFieldErrors?.[0] ?? 'ログインに失敗しました'
  } finally {
    loading.value = false
  }
}
</script>
