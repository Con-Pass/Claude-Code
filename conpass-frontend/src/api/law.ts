import api from './client'

export interface LawFileInfo {
  id: number
  filename: string
  url: string
  created_at: string
}

export interface LawDocument {
  id: number
  law_name: string
  law_short_name: string
  law_number: string
  effective_date: string | null
  status: 'PENDING' | 'INDEXED' | 'FAILED'
  article_count: number
  created_at: string
  text?: string
  applicable_contract_types: string[]
  search_keywords: string[]
  files: LawFileInfo[]
}

export const lawApi = {
  list: (): Promise<LawDocument[]> =>
    api.get('/setting/law/list').then(r => r.data),

  upload: (fd: FormData): Promise<{ id: number; status: string; article_count: number }> =>
    // Content-Type は Axios が FormData を検出して自動設定（boundary 付き）
    api.post('/setting/law/upload', fd).then(r => r.data),

  delete: (id: number): Promise<void> =>
    api.delete(`/setting/law/${id}`).then(() => undefined),

  reindex: (id: number): Promise<{ status: string; article_count: number }> =>
    api.post(`/setting/law/${id}/reindex`).then(r => r.data),

  getDetail: (id: number): Promise<LawDocument> =>
    api.get(`/setting/law/${id}`).then(r => r.data),

  update: (id: number, fd: FormData): Promise<LawDocument> =>
    api.patch(`/setting/law/${id}`, fd).then(r => r.data),

  deleteFile: (fileId: number): Promise<void> =>
    api.delete(`/setting/law/file/${fileId}/delete`).then(() => undefined),
}
