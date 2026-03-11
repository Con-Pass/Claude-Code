<template>
  <AppLayout>
    <div v-if="loading" style="color:#718096; padding:40px 0; text-align:center;">読み込み中...</div>

    <div v-else-if="loadError" class="error-msg" style="max-width:480px;">
      {{ loadError }}
      <button class="btn btn-ghost" style="margin-left:12px;" @click="router.back()">戻る</button>
    </div>

    <template v-else-if="contract">
      <!-- パンくず -->
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:20px; font-size:13px; color:#718096;">
        <span style="cursor:pointer; color:#2563eb;" @click="router.push('/contracts')">契約書一覧</span>
        <span>›</span>
        <span style="color:#2d3748;">{{ contract.name }}</span>
      </div>

      <!-- ヘッダーカード -->
      <div class="card" style="margin-bottom:20px; display:flex; align-items:flex-start; justify-content:space-between; gap:16px;">
        <div>
          <h1 style="font-size:20px; font-weight:700; margin-bottom:8px;">{{ contract.name }}</h1>
          <div style="display:flex; gap:10px; flex-wrap:wrap;">
            <span class="badge" :class="statusBadge(contract.status)">{{ statusLabel(contract.status) }}</span>
            <span class="badge badge-blue">{{ contract.isProvider ? '自社提供' : '相手方提供' }}</span>
          </div>
        </div>
        <button class="btn btn-primary" @click="showUpload = true">
          ＋ ファイルをアップロード
        </button>
      </div>

      <!-- 2カラムレイアウト（基本情報） -->
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:20px;">
        <div class="card">
          <h2 class="section-title">基本情報</h2>
          <table class="info-table">
            <tbody>
              <tr>
                <th>取引先法人</th>
                <td>{{ contract.client?.corporateName ?? '-' }}</td>
              </tr>
              <tr>
                <th>フォルダ</th>
                <td>{{ contract.directory?.name ?? '-' }}</td>
              </tr>
              <tr>
                <th>バージョン</th>
                <td>{{ contract.version ?? '-' }}</td>
              </tr>
              <tr>
                <th>作成日</th>
                <td>{{ formatDate(contract.createdAt) }}</td>
              </tr>
              <tr>
                <th>更新日</th>
                <td>{{ formatDate(contract.updatedAt) }}</td>
              </tr>
              <tr v-if="contract.createdBy">
                <th>登録者</th>
                <td>{{ contract.createdBy?.name ?? '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="card">
          <h2 class="section-title">紐づき情報</h2>
          <table class="info-table">
            <tbody>
              <tr>
                <th>テンプレート</th>
                <td>{{ contract.template?.name ?? '-' }}</td>
              </tr>
              <tr>
                <th>元契約書</th>
                <td>{{ contract.origin?.name ?? '-' }}</td>
              </tr>
              <tr>
                <th>公開設定</th>
                <td>{{ contract.isOpen ? '公開' : '非公開' }}</td>
              </tr>
              <tr>
                <th>ゴミ箱</th>
                <td>{{ contract.isGarbage ? 'あり' : 'なし' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- タブ付きコンテンツ -->
      <div class="card" style="margin-bottom:20px;">
        <!-- タブバー -->
        <div class="tab-bar" style="align-items: center;">
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'preview' }"
            @click="activeTab = 'preview'"
          >ファイルプレビュー</button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'text' }"
            @click="switchToText"
          >テキスト全文</button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'meta' }"
            @click="switchToMeta"
          >メタ情報</button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'relations' }"
            @click="switchToRelations"
          >関連契約</button>
          <!-- 再抽出ボタン（右端） -->
          <div style="margin-left: auto; display: flex; align-items: center; gap: 8px; padding-right: 4px;">
            <span v-if="rescanMessage"
              :style="{ fontSize: '12px', color: rescanMessage.startsWith('✓') ? '#38a169' : '#e53e3e' }">
              {{ rescanMessage }}
            </span>
            <button
              class="btn btn-ghost"
              style="font-size: 12px; padding: 4px 10px; white-space: nowrap;"
              :disabled="rescanning"
              @click="rescan"
              title="テキストとメタ情報を再抽出"
            >
              <span v-if="rescanning" style="display: flex; align-items: center; gap: 4px;">
                <span style="display: inline-block; animation: spin 1s linear infinite;">⏳</span>
                抽出中...
              </span>
              <span v-else>🔄 再抽出</span>
            </button>
          </div>
        </div>

        <!-- 再抽出進行バー -->
        <div v-if="rescanning" class="rescan-progress-section">
          <div
            v-for="(step, i) in rescanStepDefs"
            :key="i"
            class="rescan-step-row"
            :class="{ 'step-done': isStepDone(step.max), 'step-active': isStepActive(step.min, step.max) }"
          >
            <span class="step-num">{{ isStepDone(step.max) ? '✓' : i + 1 }}</span>
            <span class="step-name">{{ step.label }}</span>
            <div class="step-bar-track">
              <div
                class="step-bar-fill"
                :class="{ shimmer: isStepActive(step.min, step.max) }"
                :style="{ width: stepBarWidth(step.min, step.max) }"
              ></div>
            </div>
            <span class="step-status-text">
              {{ isStepDone(step.max) ? '完了' : isStepActive(step.min, step.max) ? '処理中...' : '待機中' }}
            </span>
          </div>
        </div>

        <!-- 抽出状況バー（通常時） -->
        <div v-else-if="extractionStatus !== null" class="extraction-status-section">
          <div class="ext-status-row">
            <span class="ext-label">テキスト全文</span>
            <div class="ext-bar-track">
              <div class="ext-bar-fill" :class="extractionStatus.hasBody ? 'filled' : 'empty'" style="width:100%"></div>
            </div>
            <span class="ext-badge" :class="extractionStatus.hasBody ? 'badge-ok' : 'badge-none'">
              {{ extractionStatus.hasBody ? '抽出済み' : '未抽出' }}
            </span>
          </div>
          <div class="ext-status-row">
            <span class="ext-label">メタ情報</span>
            <div class="ext-bar-track">
              <div
                class="ext-bar-fill"
                :class="extractionStatus.metaCount > 0 ? 'filled' : 'empty'"
                :style="{ width: extractionStatus.metaCount > 0 ? Math.min(100, extractionStatus.metaCount * 7) + '%' : '0%' }"
              ></div>
            </div>
            <span class="ext-badge" :class="extractionStatus.metaCount > 0 ? 'badge-ok' : 'badge-none'">
              {{ extractionStatus.metaCount > 0 ? extractionStatus.metaCount + '件' : '未抽出' }}
            </span>
          </div>
        </div>

        <!-- ファイルプレビュータブ -->
        <div v-if="activeTab === 'preview'" class="preview-layout">
          <!-- 左：ファイル一覧 -->
          <div class="file-list-panel">
            <div
              v-if="!contract.files?.length"
              style="color:#718096; padding:16px; text-align:center; font-size:13px;"
            >
              ファイルなし
            </div>
            <div
              v-for="f in contract.files"
              :key="f.id"
              class="file-item"
              :class="{ selected: selectedFile?.id === f.id }"
              @click="selectFile(f)"
            >
              <div style="font-size:18px; margin-bottom:4px;">{{ fileIcon(f.name) }}</div>
              <div style="font-size:12px; font-weight:500; word-break:break-all;">{{ f.name }}</div>
              <div style="font-size:11px; color:#718096; margin-top:2px;">{{ f.size ? formatSize(f.size) : '' }}</div>
            </div>
          </div>

          <!-- 右：プレビュー -->
          <div class="preview-panel">
            <div v-if="!selectedFile" class="preview-placeholder">
              左のファイルを選択するとプレビューが表示されます
            </div>
            <div v-else-if="previewLoading" class="preview-placeholder">
              <div style="font-size:24px; margin-bottom:8px;">⏳</div>
              読み込み中...
            </div>
            <template v-else>
              <!-- PDF -->
              <embed
                v-if="isPdf(selectedFile.name) && previewUrl"
                :src="previewUrl"
                type="application/pdf"
                class="preview-embed"
              />
              <!-- 画像 -->
              <img
                v-else-if="isImage(selectedFile.name) && previewUrl"
                :src="previewUrl"
                class="preview-image"
                :alt="selectedFile.name"
              />
              <!-- その他 / プレビューURL未取得 -->
              <div v-else class="preview-placeholder">
                <div style="font-size:48px; margin-bottom:12px;">{{ fileIcon(selectedFile.name) }}</div>
                <div style="font-size:13px; color:#718096; margin-bottom:12px;">{{ selectedFile.name }}</div>
                <a
                  v-if="previewUrl"
                  :href="previewUrl"
                  target="_blank"
                  class="btn btn-primary"
                >ファイルを開く</a>
              </div>
            </template>
          </div>
        </div>

        <!-- メタ情報タブ -->
        <div v-if="activeTab === 'meta'" class="meta-tab">
          <div v-if="metaLoading" style="color:#718096; padding:40px; text-align:center;">読み込み中...</div>
          <div v-else-if="metaError" style="color:#e53e3e; padding:20px;">{{ metaError }}</div>
          <div v-else-if="!metaItems.length" style="color:#718096; padding:40px; text-align:center;">
            抽出されたメタ情報がありません
          </div>
          <table v-else class="meta-table">
            <thead>
              <tr>
                <th>項目名</th>
                <th>抽出値</th>
                <th style="text-align:right;">信頼度</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in metaItems" :key="m.id">
                <td class="meta-key">{{ m.keyName }}</td>
                <td class="meta-value">{{ m.value }}</td>
                <td style="text-align:right;">
                  <div class="score-bar-wrap">
                    <div class="score-bar" :style="{ width: Math.round((m.score ?? 0) * 100) + '%' }"></div>
                    <span class="score-label">{{ m.score != null ? Math.round(m.score * 100) + '%' : '-' }}</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 関連契約タブ -->
        <div v-if="activeTab === 'relations'" class="relations-tab">
          <div v-if="relationsLoading" style="color:#718096; padding:40px; text-align:center;">読み込み中...</div>
          <div v-else-if="relationsError" style="color:#e53e3e; padding:20px;">{{ relationsError }}</div>
          <template v-else-if="relationsData">

            <!-- 親契約セクション -->
            <div class="relation-section">
              <div class="relation-section-header">
                <span class="relation-section-title">親契約</span>
                <button
                  v-if="!relationsData.parent && !showParentSearch"
                  class="btn btn-ghost btn-xs"
                  @click="showParentSearch = true"
                >+ 設定</button>
                <button
                  v-if="relationsData.parent"
                  class="btn btn-ghost btn-xs relation-remove-btn"
                  @click="clearParent"
                >解除</button>
              </div>
              <div v-if="relationsData.parent" class="relation-card">
                <div class="relation-card-name" @click="router.push(`/contracts/${relationsData.parent.id}`)">
                  {{ relationsData.parent.name }}
                </div>
                <div v-if="relationsData.parent.directory" class="relation-card-dir">{{ relationsData.parent.directory }}</div>
              </div>
              <div v-else-if="!showParentSearch" class="relation-empty">親契約なし</div>
              <div v-if="showParentSearch" class="search-panel">
                <div style="display:flex; gap:8px; margin-bottom:10px;">
                  <input v-model="parentSearchQuery" class="search-input" placeholder="契約書名で検索..." @keyup.enter="searchParent" />
                  <button class="btn btn-primary btn-xs" @click="searchParent" :disabled="parentSearchLoading">検索</button>
                  <button class="btn btn-ghost btn-xs" @click="showParentSearch = false; parentSearchQuery = ''; parentSearchResults = []">×</button>
                </div>
                <div v-if="parentSearchLoading" style="color:#718096; font-size:13px;">検索中...</div>
                <div v-else-if="parentSearchResults.length === 0 && parentSearchQuery.trim()" style="color:#718096; font-size:13px;">該当なし</div>
                <div v-for="r in parentSearchResults" :key="r.id" class="search-result-row" @click="setParent(r.id)">
                  <span>{{ r.name }}</span>
                  <span v-if="r.directory" style="color:#718096; font-size:11px; margin-left:8px;">{{ r.directory }}</span>
                </div>
              </div>
            </div>

            <!-- 子契約セクション -->
            <div class="relation-section">
              <div class="relation-section-header">
                <span class="relation-section-title">子契約 ({{ relationsData.children.length }})</span>
              </div>
              <div v-if="!relationsData.children.length" class="relation-empty">子契約なし</div>
              <div v-for="c in relationsData.children" :key="c.id" class="relation-card">
                <div class="relation-card-name" @click="router.push(`/contracts/${c.id}`)">{{ c.name }}</div>
                <div v-if="c.directory" class="relation-card-dir">{{ c.directory }}</div>
              </div>
              <div v-if="relationsData.children.length" style="margin-top:8px; font-size:11px; color:#a0aec0;">
                ※ 子契約は子側の契約書から「親契約」を設定することで登録されます
              </div>
            </div>

            <!-- 関係書類セクション -->
            <div class="relation-section">
              <div class="relation-section-header">
                <span class="relation-section-title">関係書類 ({{ relationsData.related_docs.length }})</span>
                <button v-if="!showDocSearch" class="btn btn-ghost btn-xs" @click="showDocSearch = true">+ 追加</button>
              </div>
              <div v-if="!relationsData.related_docs.length && !showDocSearch" class="relation-empty">関係書類なし</div>
              <div v-for="d in relationsData.related_docs" :key="d.id" class="relation-card">
                <div style="flex:1;">
                  <div class="relation-card-name" @click="router.push(`/contracts/${d.id}`)">{{ d.name }}</div>
                  <div v-if="d.directory" class="relation-card-dir">{{ d.directory }}</div>
                </div>
                <button class="btn btn-ghost btn-xs relation-remove-btn" @click="removeRelatedDoc(d.id)">解除</button>
              </div>
              <div v-if="showDocSearch" class="search-panel">
                <div style="display:flex; gap:8px; margin-bottom:10px;">
                  <input v-model="docSearchQuery" class="search-input" placeholder="契約書名で検索..." @keyup.enter="searchDoc" />
                  <button class="btn btn-primary btn-xs" @click="searchDoc" :disabled="docSearchLoading">検索</button>
                  <button class="btn btn-ghost btn-xs" @click="showDocSearch = false; docSearchQuery = ''; docSearchResults = []">×</button>
                </div>
                <div v-if="docSearchLoading" style="color:#718096; font-size:13px;">検索中...</div>
                <div v-else-if="docSearchResults.length === 0 && docSearchQuery.trim()" style="color:#718096; font-size:13px;">該当なし</div>
                <div v-for="r in docSearchResults" :key="r.id" class="search-result-row" @click="addRelatedDoc(r.id)">
                  <span>{{ r.name }}</span>
                  <span v-if="r.directory" style="color:#718096; font-size:11px; margin-left:8px;">{{ r.directory }}</span>
                </div>
              </div>
            </div>

          </template>
        </div>

        <!-- テキスト全文タブ -->
        <div v-if="activeTab === 'text'" class="text-tab">
          <div v-if="textLoading" style="color:#718096; padding:40px; text-align:center;">
            読み込み中...
          </div>
          <div v-else-if="textError" style="color:#e53e3e; padding:20px;">
            {{ textError }}
          </div>
          <div v-else-if="!bodyText" style="color:#718096; padding:40px; text-align:center;">
            テキストデータがありません
          </div>
          <pre v-else class="body-text">{{ bodyText }}</pre>
        </div>
      </div>

      <!-- コメント一覧 -->
      <div class="card" v-if="contract.comments?.length">
        <h2 class="section-title">コメント</h2>
        <div v-for="c in contract.comments" :key="c.id" style="padding:12px 0; border-bottom:1px solid #f0f4f8;">
          <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
            <span style="font-weight:600; font-size:13px;">{{ c.createdBy?.name ?? '不明' }}</span>
            <span style="font-size:11px; color:#718096;">{{ formatDate(c.createdAt) }}</span>
          </div>
          <div style="font-size:13px; color:#4b5563;">{{ c.comment }}</div>
        </div>
      </div>
    </template>

    <!-- アップロードモーダル -->
    <UploadModal
      v-if="showUpload && contract"
      :directory-id="contract.directory?.id ?? 0"
      @close="showUpload = false"
      @uploaded="onUploaded"
    />
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import UploadModal from '../components/UploadModal.vue'
import api from '../api/client'

const route  = useRoute()
const router = useRouter()

interface ContractDetail {
  id: number
  name: string
  status: number
  isProvider: boolean
  isOpen: boolean
  isGarbage: boolean
  version: string
  createdAt: string
  updatedAt: string
  client?: { id: number; corporateName?: string; corporateAddress?: string }
  directory?: { id: number; name: string }
  template?: { name: string }
  origin?: { name: string }
  createdBy?: { name: string }
  files?: FileItem[]
  comments?: CommentItem[]
}
interface FileItem {
  id: number
  name: string
  type: number
  size?: number
  url?: string
  createdAt?: string
  created_at?: string
}
interface CommentItem {
  id: number
  comment: string
  createdAt: string
  createdBy?: { name: string }
}

const loading    = ref(true)
const loadError  = ref('')
const contract   = ref<ContractDetail | null>(null)
const showUpload = ref(false)

// タブ
const activeTab    = ref<'preview' | 'text' | 'meta' | 'relations'>('preview')
const selectedFile = ref<FileItem | null>(null)
const previewUrl   = ref('')
const blobUrl      = ref('')   // Blob URL（解放管理用）
const previewLoading = ref(false)

// テキスト全文
const textLoading = ref(false)
const textError   = ref('')
const bodyText    = ref('')

// メタ情報
interface MetaItem {
  id: number
  keyName: string
  value: string
  score?: number
}
const metaLoading = ref(false)
const metaError   = ref('')
const metaItems   = ref<MetaItem[]>([])

// 関連契約
interface RelationBriefInfo {
  id: number
  name: string
  directory?: string
  file_id?: number
  file_name?: string
}
interface RelationsData {
  parent: RelationBriefInfo | null
  children: RelationBriefInfo[]
  related_docs: RelationBriefInfo[]
}
const relationsLoading   = ref(false)
const relationsError     = ref('')
const relationsData      = ref<RelationsData | null>(null)
const showParentSearch   = ref(false)
const parentSearchQuery  = ref('')
const parentSearchResults = ref<RelationBriefInfo[]>([])
const parentSearchLoading = ref(false)
const showDocSearch      = ref(false)
const docSearchQuery     = ref('')
const docSearchResults   = ref<RelationBriefInfo[]>([])
const docSearchLoading   = ref(false)

function isPdf(name: string)   { return name?.toLowerCase().endsWith('.pdf') }
function isImage(name: string) {
  const ext = name?.split('.').pop()?.toLowerCase() ?? ''
  return ['png','jpg','jpeg','gif','webp'].includes(ext)
}
function fileIcon(name: string) {
  const ext = name?.split('.').pop()?.toLowerCase()
  if (ext === 'pdf') return '📄'
  if (['doc','docx'].includes(ext ?? '')) return '📝'
  if (['xls','xlsx'].includes(ext ?? '')) return '📊'
  return '📎'
}
function formatSize(bytes: number) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}
function formatDate(d?: string) { return d ? d.slice(0, 10) : '-' }
function statusLabel(s: number) { return s === 1 ? '有効' : s === 2 ? '無効' : '不明' }
function statusBadge(s: number) { return s === 1 ? 'badge-green' : 'badge-gray' }

async function selectFile(f: FileItem) {
  selectedFile.value = f
  previewUrl.value = ''
  previewLoading.value = true

  // 前のBlob URLを解放してメモリリークを防ぐ
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value)
    blobUrl.value = ''
  }

  try {
    const res = await api.get('/gcs/preview', { params: { fileid: f.id } })
    const raw = res.data?.signed_url ?? ''

    if (raw.startsWith('/api/local-file')) {
      // ローカル開発: axiosでblob取得（認証クッキー付き）→ Blob URLに変換
      // <embed>が直接URLを叩くと認証やセキュリティヘッダーで拒否されるため
      const pathParam = new URL(raw, location.origin).searchParams.get('path') ?? ''
      const blobRes = await api.get('/local-file', {
        params: { path: pathParam },
        responseType: 'blob',
      })
      const contentType = blobRes.headers['content-type'] ?? 'application/pdf'
      const blob = new Blob([blobRes.data], { type: contentType })
      blobUrl.value = URL.createObjectURL(blob)
      previewUrl.value = blobUrl.value
    } else {
      // 本番: GCS署名付きURLをそのまま使用
      previewUrl.value = raw
    }
  } catch {
    previewUrl.value = ''
  } finally {
    previewLoading.value = false
  }
}

async function switchToRelations() {
  activeTab.value = 'relations'
  if (relationsData.value || relationsLoading.value) return
  await loadRelations()
}

async function loadRelations() {
  relationsLoading.value = true
  relationsError.value = ''
  try {
    const res = await api.get(`/contract/${contract.value!.id}/relations/`)
    const d = res.data
    relationsData.value = {
      parent:       d.parent ?? null,
      children:     d.children ?? [],
      related_docs: d.related_docs ?? [],
    }
  } catch (e: any) {
    relationsError.value = e?.response?.data?.detail ?? '関連契約の取得に失敗しました'
  } finally {
    relationsLoading.value = false
  }
}

async function _searchCandidates(query: string): Promise<RelationBriefInfo[]> {
  const params: any = {}
  if (query.trim()) params.search_term = query
  const res = await api.get(`/contract/account/${contract.value!.id}/`, { params })
  const list: any[] = res.data?.results ?? res.data?.list ?? res.data ?? []
  return list.map((c: any) => ({
    id:        c.id,
    name:      c.name,
    directory: c.directory ?? c.directoryName ?? c.directory_name,
  }))
}

async function searchParent() {
  if (parentSearchLoading.value) return
  parentSearchLoading.value = true
  try {
    parentSearchResults.value = await _searchCandidates(parentSearchQuery.value)
  } catch { /* ignore */ } finally {
    parentSearchLoading.value = false
  }
}

async function setParent(parentId: number) {
  try {
    await api.post(`/contract/${contract.value!.id}/parent/`, { parent_id: parentId })
    showParentSearch.value = false
    parentSearchQuery.value = ''
    parentSearchResults.value = []
    relationsData.value = null
    await loadRelations()
  } catch (e: any) {
    alert(e?.response?.data?.error ?? '親契約の設定に失敗しました')
  }
}

async function clearParent() {
  if (!confirm('親契約の紐付けを解除しますか？')) return
  try {
    await api.delete(`/contract/${contract.value!.id}/parent/`)
    relationsData.value = null
    await loadRelations()
  } catch (e: any) {
    alert(e?.response?.data?.error ?? '親契約の解除に失敗しました')
  }
}

async function searchDoc() {
  if (docSearchLoading.value) return
  docSearchLoading.value = true
  try {
    docSearchResults.value = await _searchCandidates(docSearchQuery.value)
  } catch { /* ignore */ } finally {
    docSearchLoading.value = false
  }
}

async function addRelatedDoc(docId: number) {
  try {
    await api.post(`/contract/related/${contract.value!.id}/`, { related_contract_id: docId, action: 'add' })
    showDocSearch.value = false
    docSearchQuery.value = ''
    docSearchResults.value = []
    relationsData.value = null
    await loadRelations()
  } catch (e: any) {
    alert(e?.response?.data?.error ?? '関係書類の追加に失敗しました')
  }
}

async function removeRelatedDoc(docId: number) {
  if (!confirm('この関係書類の紐付けを解除しますか？')) return
  try {
    await api.post(`/contract/related/${contract.value!.id}/`, { related_contract_id: docId, action: 'remove' })
    relationsData.value = null
    await loadRelations()
  } catch (e: any) {
    alert(e?.response?.data?.error ?? '関係書類の解除に失敗しました')
  }
}

async function switchToMeta() {
  activeTab.value = 'meta'
  if (metaItems.value.length || metaLoading.value) return
  metaLoading.value = true
  metaError.value = ''
  try {
    const res = await api.get(`/contract/${contract.value!.id}/metadata`)
    const list: any[] = res.data?.response ?? res.data?.results ?? res.data?.list ?? res.data ?? []
    metaItems.value = list.map((m: any) => ({
      id:      m.id,
      keyName: m.key?.name ?? m.keyName ?? m.key_name ?? String(m.key ?? ''),
      value:   m.value ?? '-',
      score:   m.score ?? null,
    }))
  } catch (e: any) {
    metaError.value = e?.response?.data?.detail ?? 'メタ情報の取得に失敗しました'
  } finally {
    metaLoading.value = false
  }
}

async function switchToText() {
  activeTab.value = 'text'
  if (bodyText.value || textLoading.value) return
  textLoading.value = true
  textError.value = ''
  try {
    const params: any = { id: contract.value!.id }
    if (contract.value?.version) params.version = contract.value.version
    const res = await api.get('/contract/body', { params })
    const raw = res.data?.response?.body ?? res.data?.body ?? res.data?.text ?? res.data ?? ''
    bodyText.value = typeof raw === 'string' ? decodeURIComponent(raw) : JSON.stringify(raw, null, 2)
  } catch (e: any) {
    textError.value = e?.response?.data?.detail ?? 'テキストの取得に失敗しました'
  } finally {
    textLoading.value = false
  }
}

async function fetchContract() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await api.get('/contract', { params: { id: route.params.id, type: 1 } })
    const raw = res.data?.response ?? res.data
    contract.value = {
      id:         raw.id,
      name:       raw.name,
      status:     raw.status,
      isProvider: raw.isProvider ?? raw.is_provider,
      isOpen:     raw.isOpen ?? raw.is_open,
      isGarbage:  raw.isGarbage ?? raw.is_garbage,
      version:    raw.version,
      createdAt:  raw.createdAt ?? raw.created_at,
      updatedAt:  raw.updatedAt ?? raw.updated_at,
      client:     raw.client,
      directory:  raw.directory,
      template:   raw.template,
      origin:     raw.origin,
      createdBy:  raw.createdBy ?? raw.created_by,
      files:      raw.files ?? [],
      comments:   raw.comments ?? [],
    }
    // ファイルがあれば最初のものを選択してプレビューURLを取得
    const firstFile = contract.value.files?.[0]
    if (firstFile) selectFile(firstFile)
    // 抽出状況を取得
    await fetchExtractionStatus()
  } catch (e: any) {
    loadError.value = e?.response?.data?.detail ?? '契約書の取得に失敗しました'
  } finally {
    loading.value = false
  }
}

function onUploaded() {
  showUpload.value = false
  bodyText.value = ''    // テキストキャッシュをクリア
  metaItems.value = []   // メタ情報キャッシュをクリア
  fetchContract()
}

// 抽出ステータス
interface ExtractionStatus { hasBody: boolean; metaCount: number }
const extractionStatus = ref<ExtractionStatus | null>(null)

async function fetchExtractionStatus() {
  if (!contract.value) return
  try {
    const res = await api.get(`/contract/${contract.value.id}/extraction-status`)
    extractionStatus.value = res.data
  } catch { /* ignore */ }
}

// 再抽出進行状況
const rescanProgress = ref(0)  // 0–100
let progressTimer: ReturnType<typeof setInterval> | null = null

const rescanStepDefs = [
  { label: 'OCR・テキスト解析', min: 0,  max: 35  },
  { label: 'エンティティ抽出',  min: 35, max: 70  },
  { label: 'データ保存',        min: 70, max: 100 },
]

function stepBarWidth(min: number, max: number): string {
  const w = Math.min(100, Math.max(0, (rescanProgress.value - min) / (max - min) * 100))
  return w.toFixed(1) + '%'
}
function isStepDone(max: number)                   { return rescanProgress.value >= max }
function isStepActive(min: number, max: number)    { return rescanProgress.value >= min && rescanProgress.value < max }

function startProgressTimer() {
  rescanProgress.value = 0
  progressTimer = setInterval(() => {
    const p = rescanProgress.value
    if (p < 90) {
      const rate = p < 30 ? 1.2 : p < 60 ? 0.7 : 0.25
      rescanProgress.value = Math.min(90, p + rate)
    }
  }, 100)
}

function stopProgressTimer(success: boolean) {
  if (progressTimer !== null) { clearInterval(progressTimer); progressTimer = null }
  rescanProgress.value = success ? 100 : 0
}

// 再抽出
const rescanning    = ref(false)
const rescanMessage = ref('')

async function rescan() {
  if (!contract.value || rescanning.value) return
  rescanning.value = true
  rescanMessage.value = ''
  startProgressTimer()
  try {
    await api.post(`/contract/${contract.value.id}/rescan`)
    stopProgressTimer(true)
    bodyText.value  = ''
    metaItems.value = []
    await fetchExtractionStatus()
    rescanMessage.value = '✓ 再抽出完了'
    if (activeTab.value === 'text') {
      textLoading.value = false
      await switchToText()
    } else if (activeTab.value === 'meta') {
      metaLoading.value = false
      await switchToMeta()
    }
  } catch (e: any) {
    stopProgressTimer(false)
    rescanMessage.value = e?.response?.data?.detail ?? '再抽出に失敗しました'
  } finally {
    rescanning.value = false
    setTimeout(() => { rescanMessage.value = '' }, 4000)
  }
}

onMounted(fetchContract)
</script>

<style scoped>
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #4b5563;
  margin-bottom: 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f4f8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.info-table { width: 100%; border-collapse: collapse; }
.info-table th {
  width: 110px;
  padding: 8px 0;
  font-size: 12px;
  color: #718096;
  font-weight: 500;
  vertical-align: top;
}
.info-table td {
  padding: 8px 0;
  font-size: 13px;
  border-bottom: none;
}
.info-table tr:not(:last-child) th,
.info-table tr:not(:last-child) td {
  border-bottom: 1px solid #f8fafc;
}

/* タブ */
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 2px solid #e2e8f0;
  margin-bottom: 20px;
}
.tab-btn {
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 500;
  color: #718096;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.tab-btn:hover { color: #2563eb; }
.tab-btn.active {
  color: #2563eb;
  border-bottom-color: #2563eb;
  font-weight: 600;
}

/* プレビューレイアウト */
.preview-layout {
  display: flex;
  gap: 16px;
  min-height: 480px;
}
.file-list-panel {
  width: 180px;
  flex-shrink: 0;
  border-right: 1px solid #e2e8f0;
  overflow-y: auto;
}
.file-item {
  padding: 12px 10px;
  cursor: pointer;
  border-radius: 6px;
  margin: 4px;
  text-align: center;
  transition: background 0.15s;
}
.file-item:hover { background: #f0f4f8; }
.file-item.selected { background: #ebf4ff; }

.preview-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 480px;
}
.preview-embed {
  width: 100%;
  height: 600px;
  border: none;
}
.preview-image {
  max-width: 100%;
  max-height: 600px;
  object-fit: contain;
}
.preview-placeholder {
  text-align: center;
  color: #a0aec0;
  font-size: 14px;
  padding: 40px;
}

/* メタ情報タブ */
.meta-tab { min-height: 200px; }
.meta-table { width: 100%; border-collapse: collapse; }
.meta-table th {
  padding: 8px 12px;
  font-size: 11px;
  font-weight: 600;
  color: #718096;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 2px solid #e2e8f0;
  background: #f8fafc;
}
.meta-table td { padding: 10px 12px; border-bottom: 1px solid #f0f4f8; vertical-align: middle; }
.meta-key { font-size: 12px; color: #718096; font-weight: 500; width: 160px; }
.meta-value { font-size: 13px; color: #2d3748; font-weight: 500; }
.score-bar-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}
.score-bar {
  height: 6px;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 3px;
  min-width: 2px;
  max-width: 80px;
  transition: width 0.3s;
}
.score-label { font-size: 11px; color: #718096; min-width: 30px; text-align: right; }

/* テキスト全文 */
.text-tab {
  min-height: 300px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* 抽出状況バー */
.extraction-status-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 0 16px;
  border-bottom: 1px solid #f0f4f8;
  margin-bottom: 16px;
}
.ext-status-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}
.ext-label {
  width: 80px;
  color: #718096;
  font-weight: 500;
  flex-shrink: 0;
}
.ext-bar-track {
  flex: 1;
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
}
.ext-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s ease;
}
.ext-bar-fill.filled { background: linear-gradient(90deg, #6366f1, #8b5cf6); }
.ext-bar-fill.empty  { background: transparent; }
.ext-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
  min-width: 60px;
  text-align: center;
}
.badge-ok   { background: #e6fffa; color: #38a169; }
.badge-none { background: #f7fafc; color: #a0aec0; }

/* 再抽出進行バー */
.rescan-progress-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 0 16px;
  border-bottom: 1px solid #f0f4f8;
  margin-bottom: 16px;
}
.rescan-step-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #a0aec0;
  transition: color 0.3s;
}
.rescan-step-row.step-active { color: #4a5568; }
.rescan-step-row.step-done   { color: #38a169; }
.step-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
  transition: background 0.3s, color 0.3s;
}
.step-active .step-num { background: #6366f1; color: white; }
.step-done   .step-num { background: #38a169; color: white; }
.step-name {
  width: 130px;
  font-weight: 500;
  flex-shrink: 0;
}
.step-bar-track {
  flex: 1;
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
}
.step-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 3px;
  transition: width 0.15s linear;
}
.step-bar-fill.shimmer {
  background: linear-gradient(90deg, #6366f1 20%, #a78bfa 50%, #6366f1 80%);
  background-size: 200% 100%;
  animation: shimmer-slide 1.2s linear infinite;
}
.step-status-text {
  width: 52px;
  text-align: right;
  font-size: 11px;
}
@keyframes shimmer-slide {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.body-text {
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
  line-height: 1.7;
  color: #2d3748;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 16px;
  max-height: 600px;
  overflow-y: auto;
  margin: 0;
}

/* 関連契約タブ */
.relations-tab { min-height: 200px; }
.relation-section {
  padding: 16px 0;
  border-bottom: 1px solid #f0f4f8;
}
.relation-section:last-child { border-bottom: none; }
.relation-section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.relation-section-title {
  font-size: 12px;
  font-weight: 600;
  color: #718096;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  flex: 1;
}
.btn-xs {
  font-size: 11px;
  padding: 3px 10px;
}
.relation-remove-btn { color: #e53e3e; }
.relation-card {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  margin-bottom: 6px;
  background: #f8fafc;
}
.relation-card-name {
  font-size: 13px;
  font-weight: 500;
  color: #2563eb;
  cursor: pointer;
  flex: 1;
}
.relation-card-name:hover { text-decoration: underline; }
.relation-card-dir {
  font-size: 11px;
  color: #a0aec0;
  margin-top: 2px;
}
.relation-empty {
  font-size: 13px;
  color: #a0aec0;
  padding: 6px 0;
}
.search-panel {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
  margin-top: 8px;
}
.search-input {
  flex: 1;
  padding: 5px 10px;
  font-size: 13px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  outline: none;
}
.search-input:focus { border-color: #2563eb; }
.search-result-row {
  display: flex;
  align-items: center;
  padding: 7px 10px;
  font-size: 13px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.12s;
}
.search-result-row:hover { background: #ebf4ff; }
</style>
