import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  withCredentials: true, // JWT cookie (auth-token) を送信
  headers: {
    'X-Frontend-Env': 'local', // ローカル開発: secure=false のcookieを発行させる
  },
})

export default api

// ---- 型定義 ----

export interface Contract {
  id: number
  name: string
  status: number
  clientName?: string
  directoryName?: string
  createdAt: string
  updatedAt: string
}

export interface PlaybookTemplate {
  id: number
  name: string
  industry: string
  description: string
}

export interface TenantPlaybook {
  id: number
  name: string
  yourSide: string
  isActive: boolean
  templateName?: string
}

export interface DashboardInfo {
  label: string
  count: number
}
