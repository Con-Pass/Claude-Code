<template>
  <div class="overlay" @click.self="tryClose">
    <div class="modal">

      <!-- ヘッダー -->
      <div class="modal-head">
        <div>
          <div class="modal-title">契約書ファイルを取り込む</div>
          <div class="modal-sub">OCRでテキスト化・メタ情報を自動抽出します</div>
        </div>
        <button class="close-btn" @click="tryClose">✕</button>
      </div>

      <!-- ドロップゾーン -->
      <div
        class="dropzone"
        :class="{ dragover: isDragOver, compact: queue.length > 0 }"
        @dragover.prevent="isDragOver = true"
        @dragleave.prevent="isDragOver = false"
        @drop.prevent="onDrop"
        @click="fileInputRef?.click()"
      >
        <input
          ref="fileInputRef"
          type="file"
          accept=".pdf,.doc,.docx,.xls,.xlsx,.txt"
          multiple
          style="display:none"
          @change="onFileChange"
        />
        <div class="dz-icon">{{ isDragOver ? '📂' : '☁' }}</div>
        <div class="dz-text">クリックまたはドラッグ&ドロップ</div>
        <div class="dz-hint">PDF・Word・Excel 対応 ／ 複数同時選択可</div>
      </div>

      <!-- ファイルキュー -->
      <div v-if="queue.length" class="queue">
        <div class="queue-header">
          <span>{{ queue.length }} 件選択中</span>
          <button v-if="!isUploading" class="clear-btn" @click="queue = []">すべて削除</button>
        </div>

        <div class="queue-list">
          <div v-for="item in queue" :key="item.id" class="queue-item">
            <div class="qi-icon">{{ fileIcon(item.file.name) }}</div>
            <div class="qi-info">
              <div class="qi-name">{{ item.file.name }}</div>
              <div class="qi-meta">{{ formatSize(item.file.size) }}</div>
              <!-- プログレスバー -->
              <div v-if="item.status === 'uploading'" class="qi-progress">
                <div class="qi-bar" :style="{ width: item.progress + '%' }"></div>
              </div>
            </div>
            <div class="qi-status">
              <span v-if="item.status === 'pending'"   class="badge badge-gray">待機中</span>
              <span v-if="item.status === 'uploading'" class="badge badge-blue">処理中</span>
              <span v-if="item.status === 'done'"      class="badge badge-green">完了 ✓</span>
              <span v-if="item.status === 'error'" class="badge badge-red">エラー ✕</span>
              <div v-if="item.status === 'error' && item.error" style="font-size:11px;color:#e53e3e;margin-top:4px;max-width:160px;word-break:break-all;">{{ item.error }}</div>
              <button
                v-if="item.status === 'pending'"
                class="remove-btn"
                @click="removeItem(item.id)"
              >✕</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 設定エリア -->
      <div class="settings" v-if="queue.length && !doneAll">
        <div class="setting-row">
          <label class="setting-label">保存フォルダ</label>
          <select class="input" v-model="selectedDirId" :disabled="isUploading">
            <option :value="0">フォルダを選択（任意）</option>
            <option v-for="d in directories" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>
        <div class="setting-row">
          <label class="setting-label">提供区分</label>
          <div class="toggle-group">
            <button
              class="toggle-btn"
              :class="{ active: isProvider === 1 }"
              :disabled="isUploading"
              @click="isProvider = 1"
            >自社提供</button>
            <button
              class="toggle-btn"
              :class="{ active: isProvider === 0 }"
              :disabled="isUploading"
              @click="isProvider = 0"
            >相手方提供</button>
          </div>
        </div>
      </div>

      <!-- 完了サマリー -->
      <div v-if="doneAll" class="summary">
        <div class="summary-icon">{{ errorCount === 0 ? '✅' : '⚠️' }}</div>
        <div v-if="errorCount === 0" class="summary-text">
          {{ doneCount }} 件を取り込みました。<br>
          <span style="font-size:12px; color:#718096;">バックグラウンドでOCR・メタ情報抽出を実行中です。</span>
        </div>
        <div v-else class="summary-text">
          {{ doneCount }} 件成功・{{ errorCount }} 件失敗
        </div>
      </div>

      <!-- フッター -->
      <div class="modal-foot">
        <button class="btn btn-ghost" @click="tryClose" :disabled="isUploading">
          {{ doneAll ? '閉じる' : 'キャンセル' }}
        </button>
        <button
          v-if="!doneAll"
          class="btn btn-primary"
          :disabled="queue.length === 0 || isUploading"
          @click="startUpload"
        >
          <span v-if="isUploading">取り込み中... ({{ uploadedCount }}/{{ queue.length }})</span>
          <span v-else>取り込み開始</span>
        </button>
        <button v-else class="btn btn-primary" @click="emit('imported')">
          一覧を更新
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '../api/client'

const emit = defineEmits<{ close: []; imported: [] }>()

interface QueueItem {
  id: number
  file: File
  status: 'pending' | 'uploading' | 'done' | 'error'
  progress: number
  error?: string
}

interface Directory { id: number; name: string }

const fileInputRef  = ref<HTMLInputElement | null>(null)
const isDragOver    = ref(false)
const queue         = ref<QueueItem[]>([])
const directories   = ref<Directory[]>([])
const selectedDirId = ref(0)
const isProvider    = ref(1)
const isUploading   = ref(false)
let nextId = 1

const uploadedCount = computed(() => queue.value.filter(q => q.status === 'done' || q.status === 'error').length)
const doneCount     = computed(() => queue.value.filter(q => q.status === 'done').length)
const errorCount    = computed(() => queue.value.filter(q => q.status === 'error').length)
const doneAll       = computed(() => queue.value.length > 0 && uploadedCount.value === queue.value.length)

function addFiles(files: FileList | File[]) {
  Array.from(files).forEach(f => {
    queue.value.push({ id: nextId++, file: f, status: 'pending', progress: 0 })
  })
}
function onDrop(e: DragEvent) {
  isDragOver.value = false
  if (e.dataTransfer?.files.length) addFiles(e.dataTransfer.files)
}
function onFileChange(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files?.length) addFiles(files)
  ;(e.target as HTMLInputElement).value = ''
}
function removeItem(id: number) {
  queue.value = queue.value.filter(q => q.id !== id)
}
function tryClose() {
  if (!isUploading.value) emit('close')
}

function fileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase()
  if (ext === 'pdf') return '📄'
  if (['doc','docx'].includes(ext ?? '')) return '📝'
  if (['xls','xlsx'].includes(ext ?? '')) return '📊'
  return '📎'
}
function formatSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

async function startUpload() {
  isUploading.value = true
  for (const item of queue.value) {
    if (item.status !== 'pending') continue
    item.status = 'uploading'
    item.progress = 0
    try {
      const form = new FormData()
      form.append('blob', item.file)
      form.append('filename', item.file.name)
      form.append('datatype', '3')
      form.append('directoryId', String(selectedDirId.value))
      form.append('isProvider', String(isProvider.value))
      form.append('isMetaCheck', '1')

      console.log('[Upload] dirId:', selectedDirId.value, 'file:', item.file.name, item.file.size, item.file.type)

      // 疑似プログレス
      const timer = setInterval(() => {
        if (item.progress < 85) item.progress += 15
      }, 400)

      const res = await api.post('/upload/contract', form)
      console.log('[Upload] success:', res.data)

      clearInterval(timer)
      item.progress = 100
      item.status = 'done'
    } catch (e: any) {
      console.error('[Upload] error:', e)
      item.status = 'error'
      const errData = e?.response?.data
      if (errData) {
        item.error = errData?.message ?? errData?.detail ?? errData?.blank?.[0]
          ?? (typeof errData === 'string' ? errData : JSON.stringify(errData))
      } else {
        item.error = `${e?.message ?? 'ネットワークエラー'} (status: ${e?.response?.status ?? 'no response'})`
      }
    }
  }
  isUploading.value = false
}

onMounted(async () => {
  try {
    const res = await api.get('/setting/directory/all')
    directories.value = (res.data?.response ?? res.data ?? []).map((d: any) => ({
      id: d.id, name: d.name,
    }))
    if (directories.value[0]) selectedDirId.value = directories.value[0].id
  } catch { /* フォルダ取得失敗は無視 */ }
})
</script>

<style scoped>
.overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 300;
}
.modal {
  background: #fff;
  border-radius: 14px;
  width: 580px;
  max-width: 96vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 12px 48px rgba(0,0,0,0.2);
  overflow: hidden;
}

/* ヘッダー */
.modal-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid #e8ecf0;
  flex-shrink: 0;
}
.modal-title { font-size: 16px; font-weight: 700; color: #1a202c; }
.modal-sub   { font-size: 12px; color: #718096; margin-top: 3px; }
.close-btn {
  background: none; border: none; cursor: pointer;
  font-size: 16px; color: #718096; padding: 2px 6px; border-radius: 4px;
}
.close-btn:hover { background: #f0f4f8; color: #1a202c; }

/* ドロップゾーン */
.dropzone {
  margin: 20px 24px 0;
  border: 2px dashed #c7d2fe;
  border-radius: 12px;
  padding: 36px 24px;
  text-align: center;
  cursor: pointer;
  background: #fafafe;
  transition: border-color 0.15s, background 0.15s;
  flex-shrink: 0;
}
.dropzone:hover, .dropzone.dragover {
  border-color: #6366f1;
  background: #ede9fe;
}
.dropzone.compact { padding: 18px 24px; }
.dz-icon { font-size: 36px; margin-bottom: 8px; }
.dropzone.compact .dz-icon { font-size: 24px; margin-bottom: 4px; }
.dz-text { font-size: 14px; font-weight: 600; color: #4b5563; margin-bottom: 4px; }
.dropzone.compact .dz-text { font-size: 13px; }
.dz-hint { font-size: 12px; color: #9ca3af; }
.dropzone.compact .dz-hint { display: none; }

/* ファイルキュー */
.queue {
  flex: 1;
  overflow-y: auto;
  margin: 14px 24px 0;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}
.queue-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 12px; color: #718096; font-weight: 600;
}
.clear-btn {
  background: none; border: none; cursor: pointer;
  font-size: 12px; color: #e53e3e;
}
.queue-list { overflow-y: auto; max-height: 240px; }
.queue-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid #f0f4f8;
}
.queue-item:last-child { border-bottom: none; }
.qi-icon { font-size: 20px; flex-shrink: 0; }
.qi-info { flex: 1; min-width: 0; }
.qi-name {
  font-size: 13px; font-weight: 500; color: #2d3748;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.qi-meta { font-size: 11px; color: #a0aec0; margin-top: 2px; }
.qi-progress {
  height: 3px; background: #e2e8f0; border-radius: 2px; margin-top: 6px; overflow: hidden;
}
.qi-bar {
  height: 100%; background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 2px; transition: width 0.3s;
}
.qi-status { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.remove-btn {
  background: none; border: none; cursor: pointer;
  color: #a0aec0; font-size: 12px; padding: 2px 4px;
  border-radius: 3px;
}
.remove-btn:hover { background: #f0f4f8; color: #e53e3e; }

/* バッジ */
.badge        { display: inline-block; padding: 2px 8px; border-radius: 100px; font-size: 11px; font-weight: 600; }
.badge-gray   { background: #f0f4f8; color: #718096; }
.badge-blue   { background: #ebf4ff; color: #2563eb; }
.badge-green  { background: #d1fae5; color: #065f46; }
.badge-red    { background: #fff5f5; color: #e53e3e; }

/* 設定エリア */
.settings {
  padding: 14px 24px 0;
  display: flex; flex-direction: column; gap: 10px;
  flex-shrink: 0;
}
.setting-row { display: flex; align-items: center; gap: 14px; }
.setting-label { font-size: 12px; color: #718096; font-weight: 500; min-width: 80px; }
.toggle-group { display: flex; gap: 0; }
.toggle-btn {
  padding: 6px 16px; font-size: 13px;
  border: 1px solid #d1d5db; background: #fff; cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.toggle-btn:first-child { border-radius: 6px 0 0 6px; }
.toggle-btn:last-child  { border-radius: 0 6px 6px 0; border-left: none; }
.toggle-btn.active { background: #6366f1; color: #fff; border-color: #6366f1; }
.toggle-btn:disabled { opacity: 0.6; cursor: default; }

/* 完了サマリー */
.summary {
  margin: 14px 24px 0;
  display: flex; align-items: center; gap: 14px;
  padding: 16px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 10px;
  flex-shrink: 0;
}
.summary-icon { font-size: 28px; }
.summary-text { font-size: 13px; color: #2d3748; line-height: 1.6; }

/* フッター */
.modal-foot {
  display: flex; justify-content: flex-end; gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid #e8ecf0;
  margin-top: 16px;
  flex-shrink: 0;
}

/* input共通 */
.input {
  padding: 7px 11px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  background: #fff;
  transition: border-color 0.15s;
  width: 100%;
}
.input:focus { border-color: #6366f1; }
.input:disabled { background: #f8fafc; cursor: default; }
</style>
