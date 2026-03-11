<template>
  <div class="laws-view">
    <div class="page-header">
      <h2>法令・規制管理</h2>
      <button class="btn btn-primary" @click="openUploadModal">＋ 法令を追加</button>
    </div>

    <!-- 法令一覧 -->
    <div class="law-list">
      <div v-for="law in laws" :key="law.id" class="law-card">
        <div class="law-info">
          <span class="law-name">{{ law.law_name }}</span>
          <span v-if="law.law_short_name" class="badge">{{ law.law_short_name }}</span>
          <span :class="['status-badge', law.status.toLowerCase()]">
            {{ statusLabel(law.status) }}
          </span>
        </div>
        <div class="law-meta">
          <span>{{ law.article_count }}条文</span>
          <span v-if="law.effective_date">施行: {{ law.effective_date }}</span>
          <span>登録: {{ formatDate(law.created_at) }}</span>
        </div>

        <!-- アップロード済みファイル一覧 -->
        <div v-if="law.files && law.files.length > 0" class="law-files">
          <span class="files-label">📎 ファイル:</span>
          <div v-for="f in law.files" :key="f.id" class="file-chip">
            <a :href="f.url" target="_blank" class="file-link">{{ f.filename }}</a>
            <button class="btn-remove-file" @click="removeFile(law, f.id)" title="削除">✕</button>
          </div>
        </div>
        <div v-else class="law-files-empty">
          <span class="files-label-empty">ファイル未添付</span>
        </div>

        <div class="law-actions">
          <button class="btn btn-sm btn-ghost" @click="openEditModal(law)">編集</button>
          <button
            class="btn btn-sm btn-ghost"
            :disabled="reindexingId === law.id"
            @click="reindex(law.id)"
          >
            {{ reindexingId === law.id ? '処理中...' : '再インデックス' }}
          </button>
          <button class="btn btn-sm btn-danger" @click="deleteLaw(law.id)">削除</button>
        </div>
      </div>
      <p v-if="laws.length === 0" class="empty-message">法令が登録されていません</p>
    </div>

    <!-- ========== 編集モーダル ========== -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="closeEditModal">
      <div class="modal">
        <div class="modal-header">
          <h3>法令を編集</h3>
          <button class="btn-close" @click="closeEditModal">✕</button>
        </div>

        <div class="form-group">
          <label>法令名 <span class="required">*</span></label>
          <input v-model="editForm.law_name" placeholder="取引デジタルプラットフォーム消費者保護法" />
        </div>
        <div class="form-group">
          <label>略称</label>
          <input v-model="editForm.law_short_name" placeholder="取適法" />
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>法令番号</label>
            <input v-model="editForm.law_number" placeholder="令和3年第32号" />
          </div>
          <div class="form-group">
            <label>施行日</label>
            <input v-model="editForm.effective_date" type="date" />
          </div>
        </div>
        <div class="form-group">
          <label>対象契約種別 <span class="field-hint">（補完クエリに使用・1行1種別）</span></label>
          <textarea
            v-model="editForm.applicable_contract_types_text"
            rows="3"
            placeholder="リース契約&#10;賃貸借契約&#10;設備賃貸借契約"
          />
        </div>
        <div class="form-group">
          <label>追加検索キーワード <span class="field-hint">（契約書直接検索に使用・1行1キーワード）</span></label>
          <textarea
            v-model="editForm.search_keywords_text"
            rows="3"
            placeholder="賃貸借&#10;リース&#10;使用権資産"
          />
        </div>

        <!-- 既存ファイル一覧 -->
        <div v-if="editingLaw && editingLaw.files.length > 0" class="form-group">
          <label>添付ファイル</label>
          <div class="existing-files">
            <div v-for="f in editingLaw.files" :key="f.id" class="file-chip">
              <a :href="f.url" target="_blank" class="file-link">{{ f.filename }}</a>
              <button class="btn-remove-file" @click="removeFileFromEdit(f.id)" title="削除">✕</button>
            </div>
          </div>
        </div>

        <!-- 本文編集タブ -->
        <div class="upload-tabs">
          <button :class="['tab-btn', { active: editAddMode === 'file' }]" @click="editAddMode = 'file'">
            📄 ファイルを追加
          </button>
          <button :class="['tab-btn', { active: editAddMode === 'text' }]" @click="editAddMode = 'text'">
            📋 テキストを編集
          </button>
        </div>

        <div v-if="editAddMode === 'file'" class="form-group">
          <input
            type="file"
            accept=".pdf,.txt"
            multiple
            @change="onEditFileChange"
          />
          <ul v-if="editNewFiles.length > 0" class="file-name-list">
            <li v-for="(f, i) in editNewFiles" :key="i">{{ f.name }}</li>
          </ul>
        </div>

        <div v-else class="form-group">
          <div v-if="editTextLoading" class="text-loading">テキストを読み込み中...</div>
          <textarea
            v-else
            v-model="editForm.text"
            rows="14"
            placeholder="法令テキストをここに入力してください..."
          />
          <p v-if="!editTextLoading && editForm.text" class="text-hint">
            保存すると現在のテキストが上記内容で置き換えられ、再インデックスされます。
          </p>
        </div>

        <p v-if="editError" class="error-message">{{ editError }}</p>

        <div class="modal-actions">
          <button class="btn btn-ghost" @click="closeEditModal">キャンセル</button>
          <button class="btn btn-primary" :disabled="editSaving" @click="saveLawEdit">
            {{ editSaving ? '保存中...' : '保存する' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ========== アップロードモーダル ========== -->
    <div v-if="showUploadModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h3>法令を追加</h3>
          <button class="btn-close" @click="closeModal">✕</button>
        </div>

        <div class="form-group">
          <label>法令名 <span class="required">*</span></label>
          <input v-model="form.law_name" placeholder="取引デジタルプラットフォーム消費者保護法" />
        </div>
        <div class="form-group">
          <label>略称</label>
          <input v-model="form.law_short_name" placeholder="取適法" />
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>法令番号</label>
            <input v-model="form.law_number" placeholder="令和3年第32号" />
          </div>
          <div class="form-group">
            <label>施行日</label>
            <input v-model="form.effective_date" type="date" />
          </div>
        </div>

        <div class="form-group">
          <label>対象契約種別 <span class="field-hint">（補完クエリに使用・1行1種別）</span></label>
          <textarea
            v-model="form.applicable_contract_types_text"
            rows="3"
            placeholder="リース契約&#10;賃貸借契約&#10;設備賃貸借契約"
          />
        </div>
        <div class="form-group">
          <label>追加検索キーワード <span class="field-hint">（契約書直接検索に使用・1行1キーワード）</span></label>
          <textarea
            v-model="form.search_keywords_text"
            rows="3"
            placeholder="賃貸借&#10;リース&#10;使用権資産"
          />
        </div>

        <div class="upload-tabs">
          <button :class="['tab-btn', { active: uploadMode === 'file' }]" @click="uploadMode = 'file'">
            📄 PDFアップロード
          </button>
          <button :class="['tab-btn', { active: uploadMode === 'text' }]" @click="uploadMode = 'text'">
            📋 テキスト貼り付け
          </button>
        </div>

        <div v-if="uploadMode === 'file'" class="form-group">
          <input type="file" accept=".pdf,.txt" multiple @change="onFileChange" />
          <ul v-if="selectedFiles.length > 0" class="file-name-list">
            <li v-for="(f, i) in selectedFiles" :key="i">{{ f.name }}</li>
          </ul>
        </div>

        <div v-else class="form-group">
          <textarea
            v-model="form.text"
            rows="8"
            placeholder="法令の全文をここに貼り付けてください..."
          />
        </div>

        <p v-if="uploadError" class="error-message">{{ uploadError }}</p>

        <div class="modal-actions">
          <button class="btn btn-ghost" @click="closeModal">キャンセル</button>
          <button class="btn btn-primary" :disabled="uploading" @click="uploadLaw">
            <span v-if="uploading">インデックス作成中...</span>
            <span v-else>追加する</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { lawApi, type LawDocument } from '../api/law'

const laws            = ref<LawDocument[]>([])
const showUploadModal = ref(false)
const uploadMode      = ref<'file' | 'text'>('file')
const selectedFiles   = ref<File[]>([])
const uploading       = ref(false)
const reindexingId    = ref<number | null>(null)
const uploadError     = ref('')
const form = ref({
  law_name: '',
  law_short_name: '',
  law_number: '',
  effective_date: '',
  text: '',
  applicable_contract_types_text: '',
  search_keywords_text: '',
})

// 編集モーダル
const showEditModal  = ref(false)
const editSaving     = ref(false)
const editError      = ref('')
const editTextLoading = ref(false)
const editingLaw     = ref<LawDocument | null>(null)
const editNewFiles   = ref<File[]>([])
const editAddMode    = ref<'file' | 'text'>('file')
const editForm = ref({
  law_name: '',
  law_short_name: '',
  law_number: '',
  effective_date: '',
  text: '',
  applicable_contract_types_text: '',
  search_keywords_text: '',
})

onMounted(async () => {
  laws.value = await lawApi.list()
})

function onFileChange(e: Event) {
  selectedFiles.value = Array.from((e.target as HTMLInputElement).files ?? [])
}

function onEditFileChange(e: Event) {
  editNewFiles.value = Array.from((e.target as HTMLInputElement).files ?? [])
}

function openUploadModal() {
  showUploadModal.value = true
  uploadMode.value = 'file'
  selectedFiles.value = []
  uploadError.value = ''
  Object.assign(form.value, { law_name: '', law_short_name: '', law_number: '', effective_date: '', text: '', applicable_contract_types_text: '', search_keywords_text: '' })
}

function closeModal() {
  showUploadModal.value = false
  uploadError.value = ''
}

async function uploadLaw() {
  if (!form.value.law_name.trim()) {
    uploadError.value = '法令名は必須です'
    return
  }
  if (uploadMode.value === 'file' && selectedFiles.value.length === 0 && !form.value.text) {
    uploadError.value = 'PDFファイルまたはテキストを指定してください'
    return
  }

  uploading.value = true
  uploadError.value = ''

  try {
    const fd = new FormData()
    if (form.value.law_name)       fd.append('law_name',       form.value.law_name)
    if (form.value.law_short_name) fd.append('law_short_name', form.value.law_short_name)
    if (form.value.law_number)     fd.append('law_number',     form.value.law_number)
    if (form.value.effective_date) fd.append('effective_date', form.value.effective_date)
    fd.append('applicable_contract_types', JSON.stringify(
      form.value.applicable_contract_types_text.split('\n').map(s => s.trim()).filter(Boolean)
    ))
    fd.append('search_keywords', JSON.stringify(
      form.value.search_keywords_text.split('\n').map(s => s.trim()).filter(Boolean)
    ))
    if (uploadMode.value === 'file') {
      for (const f of selectedFiles.value) fd.append('files', f)
    } else if (form.value.text) {
      fd.append('text', form.value.text)
    }

    await lawApi.upload(fd)
    laws.value = await lawApi.list()
    closeModal()
  } catch (e: any) {
    uploadError.value = e?.response?.data?.detail ?? 'アップロードに失敗しました'
  } finally {
    uploading.value = false
  }
}

async function deleteLaw(id: number) {
  if (!confirm('この法令をシステムから削除しますか？\nQdrantのインデックスも削除されます。')) return
  await lawApi.delete(id)
  laws.value = laws.value.filter(l => l.id !== id)
}

async function openEditModal(law: LawDocument) {
  editingLaw.value = { ...law, files: [...law.files] }
  editForm.value = {
    law_name:       law.law_name,
    law_short_name: law.law_short_name,
    law_number:     law.law_number,
    effective_date: law.effective_date ?? '',
    text: '',
    applicable_contract_types_text: (law.applicable_contract_types || []).join('\n'),
    search_keywords_text:           (law.search_keywords || []).join('\n'),
  }
  editNewFiles.value = []
  editAddMode.value = 'file'
  editError.value = ''
  showEditModal.value = true

  // テキストタブ選択時のために非同期でテキストを取得
  editTextLoading.value = true
  try {
    const detail = await lawApi.getDetail(law.id)
    editForm.value.text = detail.text ?? ''
  } catch {
    // 取得失敗時は空のまま（編集は可能）
  } finally {
    editTextLoading.value = false
  }
}

function closeEditModal() {
  showEditModal.value = false
  editingLaw.value = null
  editNewFiles.value = []
}

async function removeFileFromEdit(fileId: number) {
  if (!confirm('このファイルを削除しますか？')) return
  await lawApi.deleteFile(fileId)
  if (editingLaw.value) {
    editingLaw.value.files = editingLaw.value.files.filter(f => f.id !== fileId)
  }
  // 一覧も更新
  const law = laws.value.find(l => l.id === editingLaw.value?.id)
  if (law) {
    law.files = law.files.filter(f => f.id !== fileId)
  }
}

async function removeFile(law: LawDocument, fileId: number) {
  if (!confirm('このファイルを削除しますか？')) return
  await lawApi.deleteFile(fileId)
  law.files = law.files.filter(f => f.id !== fileId)
}

async function saveLawEdit() {
  if (!editForm.value.law_name.trim()) {
    editError.value = '法令名は必須です'
    return
  }
  editSaving.value = true
  editError.value = ''
  try {
    const fd = new FormData()
    fd.append('law_name',       editForm.value.law_name)
    fd.append('law_short_name', editForm.value.law_short_name)
    fd.append('law_number',     editForm.value.law_number)
    fd.append('effective_date', editForm.value.effective_date)
    fd.append('applicable_contract_types', JSON.stringify(
      editForm.value.applicable_contract_types_text.split('\n').map(s => s.trim()).filter(Boolean)
    ))
    fd.append('search_keywords', JSON.stringify(
      editForm.value.search_keywords_text.split('\n').map(s => s.trim()).filter(Boolean)
    ))
    if (editAddMode.value === 'file') {
      for (const f of editNewFiles.value) fd.append('files', f)
    } else if (editForm.value.text.trim()) {
      fd.append('text', editForm.value.text.trim())
    }

    const updated = await lawApi.update(editingLaw.value!.id, fd)
    const idx = laws.value.findIndex(l => l.id === editingLaw.value!.id)
    if (idx !== -1) {
      laws.value[idx] = updated
    }
    closeEditModal()
  } catch (e: any) {
    editError.value = e?.response?.data?.detail ?? '保存に失敗しました'
  } finally {
    editSaving.value = false
  }
}

async function reindex(id: number) {
  reindexingId.value = id
  try {
    await lawApi.reindex(id)
    laws.value = await lawApi.list()
  } finally {
    reindexingId.value = null
  }
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    PENDING: '処理待ち',
    INDEXED: 'インデックス済',
    FAILED:  '失敗',
  }
  return map[s] ?? s
}

function formatDate(d: string): string {
  return new Date(d).toLocaleDateString('ja-JP')
}
</script>

<style scoped>
.laws-view {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
}

.law-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  background: #fff;
}

.law-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.law-name {
  font-weight: 600;
  font-size: 1rem;
}

.badge {
  background: #eff6ff;
  color: #2563eb;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 0.75rem;
}

.status-badge {
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-badge.indexed { background: #d1fae5; color: #065f46; }
.status-badge.pending { background: #fef3c7; color: #92400e; }
.status-badge.failed  { background: #fee2e2; color: #991b1b; }

.law-meta {
  display: flex;
  gap: 16px;
  font-size: 0.85rem;
  color: #6b7280;
  margin-bottom: 10px;
}

/* ファイル一覧 */
.law-files {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}

.law-files-empty {
  margin-bottom: 10px;
}

.files-label {
  font-size: 0.8rem;
  color: #6b7280;
  white-space: nowrap;
}

.files-label-empty {
  font-size: 0.8rem;
  color: #d1d5db;
  font-style: italic;
}

.file-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  padding: 2px 6px;
}

.file-link {
  font-size: 0.78rem;
  color: #2563eb;
  text-decoration: none;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-link:hover {
  text-decoration: underline;
}

.btn-remove-file {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.7rem;
  color: #9ca3af;
  padding: 0 2px;
  line-height: 1;
}

.btn-remove-file:hover {
  color: #ef4444;
}

.existing-files {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.file-name-list {
  list-style: none;
  padding: 0;
  margin: 4px 0 0;
}

.file-name-list li {
  font-size: 0.8rem;
  color: #6b7280;
  padding: 2px 0;
}

.file-name-list li::before {
  content: '📎 ';
}

.law-actions {
  display: flex;
  gap: 8px;
}

.empty-message {
  text-align: center;
  color: #9ca3af;
  padding: 32px;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #fff;
  border-radius: 12px;
  padding: 28px;
  width: 560px;
  max-width: 95vw;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.modal-header h3 {
  font-size: 1.2rem;
  font-weight: 600;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  color: #6b7280;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  margin-bottom: 4px;
}

.required { color: #ef4444; }

.form-group input,
.form-group textarea {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 0.875rem;
  box-sizing: border-box;
}

.form-group input[type="file"] {
  padding: 4px;
}

.form-group textarea { resize: vertical; }

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.upload-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.tab-btn {
  flex: 1;
  padding: 8px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #f9fafb;
  cursor: pointer;
  font-size: 0.875rem;
}

.tab-btn.active {
  background: #eff6ff;
  border-color: #2563eb;
  color: #2563eb;
  font-weight: 500;
}

.text-loading {
  text-align: center;
  color: #9ca3af;
  font-size: 0.875rem;
  padding: 24px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #f9fafb;
}

.text-hint {
  font-size: 0.78rem;
  color: #9ca3af;
  margin-top: 4px;
}

.field-hint {
  font-size: 0.75rem;
  font-weight: 400;
  color: #9ca3af;
}

.error-message {
  color: #ef4444;
  font-size: 0.875rem;
  margin-bottom: 12px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}

/* 汎用ボタン */
.btn {
  padding: 8px 16px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
}

.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: #2563eb; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #1d4ed8; }
.btn-ghost { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }
.btn-ghost:hover:not(:disabled) { background: #e5e7eb; }
.btn-danger { background: #fee2e2; color: #991b1b; }
.btn-danger:hover:not(:disabled) { background: #fecaca; }
.btn-sm { padding: 4px 10px; font-size: 0.8rem; }
</style>
