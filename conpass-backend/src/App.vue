<template>
  <div id="conpass-app">
    <!-- グローバルナビゲーションバー -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark sticky-top">
      <div class="container-fluid">
        <!-- ロゴ + キャッチコピー -->
        <router-link class="navbar-brand d-flex align-items-center" to="/">
          <strong class="me-2">ConPass</strong>
          <small class="text-muted d-none d-md-inline" style="font-size: 0.75rem;">
            契約は、力だ。
          </small>
        </router-link>

        <!-- プランバッジ -->
        <span class="badge me-3" :class="planBadgeClass">
          {{ planLabel }}
        </span>

        <!-- ハンバーガーメニュー -->
        <button
          class="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbarMain"
          aria-controls="navbarMain"
          aria-expanded="false"
          aria-label="メニュー"
        >
          <span class="navbar-toggler-icon"></span>
        </button>

        <!-- メニュー -->
        <div class="collapse navbar-collapse" id="navbarMain">
          <!-- 中小企業メニュー -->
          <ul v-if="userRole === 'sme'" class="navbar-nav me-auto">
            <li class="nav-item">
              <router-link class="nav-link" to="/dashboard" active-class="active">
                ダッシュボード
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/compliance" active-class="active">
                コンプライアンス
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/playbook" active-class="active">
                Playbook
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/rules" active-class="active">
                ルール管理
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/template/compare" active-class="active">
                テンプレート
              </router-link>
            </li>
          </ul>

          <!-- 士業メニュー -->
          <ul v-else-if="userRole === 'advisor'" class="navbar-nav me-auto">
            <li class="nav-item">
              <router-link class="nav-link" to="/advisor" active-class="active">
                顧問先管理
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/compliance" active-class="active">
                コンプライアンス
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/playbook" active-class="active">
                Playbook
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/rules" active-class="active">
                ルール管理
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/template/compare" active-class="active">
                テンプレート
              </router-link>
            </li>
          </ul>

          <!-- 管理者メニュー -->
          <ul v-else-if="userRole === 'admin'" class="navbar-nav me-auto">
            <li class="nav-item">
              <router-link class="nav-link" to="/dashboard" active-class="active">
                ダッシュボード
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/oem" active-class="active">
                OEM管理
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/compliance" active-class="active">
                コンプライアンス
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/rules" active-class="active">
                ルール管理
              </router-link>
            </li>
          </ul>

          <!-- 右側: プラン比較 + ユーザー情報 -->
          <ul class="navbar-nav">
            <li class="nav-item">
              <router-link class="nav-link" to="/plan/compare">
                プラン比較
              </router-link>
            </li>
            <li class="nav-item dropdown" v-if="userName">
              <a
                class="nav-link dropdown-toggle"
                href="#"
                id="userDropdown"
                role="button"
                data-bs-toggle="dropdown"
                aria-expanded="false"
              >
                {{ userName }}
              </a>
              <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="userDropdown">
                <li>
                  <router-link class="dropdown-item" to="/onboarding">
                    はじめに
                  </router-link>
                </li>
                <li><hr class="dropdown-divider" /></li>
                <li>
                  <a class="dropdown-item" href="#" @click.prevent="logout">
                    ログアウト
                  </a>
                </li>
              </ul>
            </li>
          </ul>
        </div>
      </div>
    </nav>

    <!-- グローバルエラー表示 -->
    <div v-if="globalError" class="alert alert-danger alert-dismissible m-3" role="alert">
      {{ globalError }}
      <button type="button" class="btn-close" @click="globalError = null" aria-label="閉じる"></button>
    </div>

    <!-- メインコンテンツ -->
    <main>
      <router-view />
    </main>

    <!-- フッター -->
    <footer class="bg-light text-center text-muted py-3 mt-4 border-top">
      <small>ConPass - 契約管理プラットフォーム</small>
    </footer>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'App',

  data() {
    return {
      userRole: 'sme',     // 'sme' | 'advisor' | 'admin'
      userName: '',
      userPlan: 'light',   // 'light' | 'st' | 'st_plus'
      globalError: null,
    }
  },

  computed: {
    planLabel() {
      const labels = { light: 'Light', st: 'ST', st_plus: 'ST+' }
      return labels[this.userPlan] || 'Light'
    },
    planBadgeClass() {
      const classes = {
        light: 'bg-secondary',
        st: 'bg-primary',
        st_plus: 'bg-warning text-dark'
      }
      return classes[this.userPlan] || 'bg-secondary'
    },
  },

  created() {
    this.fetchUserInfo()
    this.setupGlobalErrorHandler()
  },

  methods: {
    async fetchUserInfo() {
      try {
        const res = await axios.get('/api/user')
        const user = res.data
        this.userName = user.name || user.lastName || ''
        // ユーザータイプからロール判定
        // ACCOUNT(1) = sme, CLIENT(2) = advisor, ADMIN(3) = admin
        const typeMap = { 1: 'sme', 2: 'advisor', 3: 'admin' }
        this.userRole = typeMap[user.userType || user.type] || 'sme'
        this.userPlan = user.plan || user.accountPlan || 'light'
      } catch (err) {
        // 未認証の場合はデフォルトのまま
        console.warn('ユーザー情報の取得に失敗:', err)
      }
    },

    setupGlobalErrorHandler() {
      // axiosグローバルインターセプター
      axios.interceptors.response.use(
        response => response,
        error => {
          if (error.response && error.response.status >= 500) {
            this.globalError = 'サーバーエラーが発生しました。しばらく経ってからもう一度お試しください。'
            // 5秒後に自動消去
            setTimeout(() => { this.globalError = null }, 5000)
          }
          return Promise.reject(error)
        }
      )
    },

    async logout() {
      try {
        await axios.post('/api/auth/logout')
      } catch {
        // ログアウト失敗してもリダイレクトする
      }
      window.location.href = '/auth/login'
    },
  },
}
</script>

<style>
#conpass-app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
#conpass-app main {
  flex: 1;
}
#conpass-app footer {
  flex-shrink: 0;
}
</style>
