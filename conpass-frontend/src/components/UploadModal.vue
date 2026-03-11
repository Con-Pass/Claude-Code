<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-box">
      <div class="modal-header">
        <h3>ファイルアップロード</h3>
        <button class="modal-close" @click="$emit('close')">✕</button>
      </div>

      <!-- ドロップゾーン -->
      <div
        class="dropzone"
        :class="{ dragover: isDragOver, 'has-file': selectedFile }"
        @dragover.prevent="isDragOver = true"
        @dragleave="isDragOver = false"
        @drop.prevent="onDrop"
        @click="fileInputRef?.click()"
      >
        <input ref="fileInputRef" type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt" style="display:none" @change="onFileChange" />
        <div v-if="!selectedFile">
          <div style="font-size:32px; margin-bottom:8px;">📎</div>
          <div style="font-weight:500; margin-bottom:4px;">クリックまたはドラッグ&ドロップ</div>
          <div style="font-size:12px; color:#718096;">PDF, Word, Excel, テキスト対応</div>
        </div>
        <div v-else style="display:flex; align-items:center; gap:12px;">
          <span style="font-size:28px;">{{ fileIcon(selectedFile.name) }}</span>
          <div>
            <div style="font-weight:500;">{{ selectedFile.name }}</div>
            <div style="font-size:12px; color:#718096;">{{ formatSize(selectedFile.size) }}</div>
          </div>
          <button class="btn btn-ghost" style="margin-left:auto;" @click.stop="selectedFile = null">削除</button>
        </div>
      </div>

      <!-- エラーメッセージ -->
      <div v-if="errorMsg" class="error-msg" style="margin-top:12px;">{{ errorMsg }}</div>
      <!-- 成功メッセージ -->
      <div v-if="successMsg" style="background:#d1fae5; color:#065f46; padding:10px 14px; border-radius:6px; font-size:13px; margin-top:12px;">
        {{ successMsg }}
      </div>

      <!-- プログレスバー -->
      <div v-if="uploading" style="margin-top:16px;">
        <div style="font-size:13px; color:#718096; margin-bottom:6px;">アップロード中...</div>
        <div style="background:#e2e8f0; border-radius:4px; height:6px; overflow:hidden;">
          <div class="progress-bar" :style="{ width: progress + '%' }"></div>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn btn-ghost" @click="$emit('close')">キャンセル</button>
        <button
          class="btn btn-primary"
          :disabled="!selectedFile || uploading"
          @click="doUpload"
        >
          {{ uploading ? 'アップロード中...' : 'アップロード' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import api from '../api/client'

const props = defineProps<{ directoryId: number }>()
const emit = defineEmits<{ close: []; uploaded: [] }>()

const fileInputRef = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const isDragOver   = ref(false)
const uploading    = ref(false)
const progress     = ref(0)
const errorMsg     = ref('')
const successMsg   = ref('')

function onDrop(e: DragEvent) {
  isDragOver.value = false
  const file = e.dataTransfer?.files[0]
  if (file) selectedFile.value = file
}
function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) selectedFile.value = file
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
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

async function doUpload() {
  if (!selectedFile.value) return
  uploading.value = true
  errorMsg.value  = ''
  successMsg.value = ''
  progress.value  = 10

  const formData = new FormData()
  formData.append('blob', selectedFile.value)
  formData.append('filename', selectedFile.value.name)
  formData.append('datatype', '3')               // CONTRACT
  formData.append('directoryId', String(props.directoryId))
  formData.append('isProvider', '1')
  formData.append('isMetaCheck', '0')

  try {
    // プログレスを擬似的に進める
    const timer = setInterval(() => {
      if (progress.value < 80) progress.value += 10
    }, 300)

    await api.post('/upload/contract', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    clearInterval(timer)
    progress.value = 100
    successMsg.value = `「${selectedFile.value.name}」をアップロードしました`
    setTimeout(() => emit('uploaded'), 1500)
  } catch (e: any) {
    const msg = e?.response?.data?.message ?? e?.response?.data?.detail ?? 'アップロードに失敗しました'
    errorMsg.value = msg
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center;
  z-index: 200;
}
.modal-box {
  background: #fff;
  border-radius: 12px;
  width: 480px;
  max-width: 95vw;
  box-shadow: 0 8px 32px rgba(0,0,0,0.18);
  overflow: hidden;
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid #e8ecf0;
  font-size: 15px; font-weight: 600;
}
.modal-close {
  background: none; border: none; cursor: pointer; font-size: 16px; color: #718096;
}
.modal-close:hover { color: #1a2236; }
.modal-footer {
  display: flex; justify-content: flex-end; gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid #e8ecf0;
}

.dropzone {
  margin: 20px 24px 0;
  border: 2px dashed #d1d5db;
  border-radius: 10px;
  padding: 32px 24px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  color: #4b5563;
}
.dropzone:hover, .dropzone.dragover { border-color: #2563eb; background: #eff6ff; }
.dropzone.has-file { border-style: solid; border-color: #2563eb; text-align: left; padding: 16px 20px; }

.progress-bar {
  height: 100%;
  background: #2563eb;
  border-radius: 4px;
  transition: width 0.3s ease;
}
</style>
