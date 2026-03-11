import axios from 'axios'

// Django API（メインバックエンド）
const api = axios.create({
  baseURL: process.env.VUE_APP_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true // JWT Cookie送信
})

// Agent API（FastAPI側: チャット・OCR・法務コマンド等）
const agentApi = axios.create({
  baseURL: process.env.VUE_APP_AGENT_API_BASE_URL || '/agent/api',
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true
})

// 共通レスポンスインターセプター
function setupInterceptors(instance) {
  instance.interceptors.response.use(
    response => response,
    error => {
      if (error.response) {
        const status = error.response.status
        if (status === 401) {
          // 認証エラー: ログインページへリダイレクト
          window.location.href = '/auth/login'
        } else if (status === 403) {
          console.warn('アクセス権限がありません')
        } else if (status >= 500) {
          console.error('サーバーエラーが発生しました:', error.response.data)
        }
      }
      return Promise.reject(error)
    }
  )
}

setupInterceptors(api)
setupInterceptors(agentApi)

export default api
export { api, agentApi }
