<template>
  <AppLayout>
    <!-- ツールバー -->
    <div class="card toolbar">
      <div class="toolbar-left">
        <input
          class="input"
          v-model="searchQuery"
          placeholder="契約書名・取引先で検索..."
          style="max-width:260px;"
          @keydown.enter="doSearch"
        />
        <select class="input" v-model="statusFilter" style="max-width:130px;" @change="doSearch">
          <option value="">全ステータス</option>
          <option value="1">有効</option>
          <option value="2">無効</option>
        </select>
        <button class="btn btn-primary" @click="doSearch">検索</button>
        <button v-if="searchQuery || statusFilter" class="btn btn-ghost" @click="clearFilters">クリア</button>
      </div>
      <button class="btn btn-import" @click="showImport = true">
        <span style="font-size:15px;">↑</span>
        ファイルを取り込む
      </button>
    </div>

    <!-- テーブル -->
    <div class="card">
      <div v-if="loading" style="color:#718096; padding:20px 0;">読み込み中...</div>
      <div v-else-if="contracts.length === 0" style="color:#718096; padding:20px 0;">契約書が見つかりません</div>
      <div class="table-wrap" v-else>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>契約書名</th>
              <th>取引先</th>
              <th>フォルダ</th>
              <th>ステータス</th>
              <th>作成日</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="c in contracts"
              :key="c.id"
              class="contract-row"
              @click="router.push(`/contracts/${c.id}`)"
            >
              <td style="color:#718096;">{{ c.id }}</td>
              <td style="font-weight:500; color:#2563eb;">{{ c.name }}</td>
              <td>{{ c.clientName ?? '-' }}</td>
              <td>{{ c.directoryName ?? '-' }}</td>
              <td><span class="badge" :class="statusBadge(c.status)">{{ statusLabel(c.status) }}</span></td>
              <td>{{ formatDate(c.createdAt) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ページネーション -->
      <div class="pagination" v-if="totalPages > 1">
        <button class="page-btn" :disabled="currentPage === 1" @click="goPage(currentPage - 1)">＜</button>
        <button
          v-for="p in visiblePages"
          :key="p"
          class="page-btn"
          :class="{ active: p === currentPage }"
          @click="goPage(p)"
        >{{ p }}</button>
        <button class="page-btn" :disabled="currentPage === totalPages" @click="goPage(currentPage + 1)">＞</button>
      </div>
      <div style="color:#718096; font-size:12px; margin-top:10px; text-align:right;" v-if="total > 0">
        全 {{ total }} 件
      </div>
    </div>

    <!-- ファイル取り込みモーダル -->
    <FileImportModal
      v-if="showImport"
      @close="showImport = false"
      @imported="onImported"
    />
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import FileImportModal from '../components/FileImportModal.vue'
import api from '../api/client'

const router = useRouter()

interface Row {
  id: number
  name: string
  status: number
  directoryId: number
  clientName?: string
  directoryName?: string
  createdAt: string
}

const contracts    = ref<Row[]>([])
const loading      = ref(true)
const currentPage  = ref(1)
const total        = ref(0)
const pageSize     = 20
const searchQuery  = ref('')
const statusFilter = ref('')
const showImport   = ref(false)

const totalPages = computed(() => Math.ceil(total.value / pageSize) || 1)
const visiblePages = computed(() => {
  const pages: number[] = []
  const start = Math.max(1, currentPage.value - 2)
  const end   = Math.min(totalPages.value, currentPage.value + 2)
  for (let i = start; i <= end; i++) pages.push(i)
  return pages
})

function formatDate(d: string) { return d ? d.slice(0, 10) : '-' }
function statusLabel(s: number) { return s === 1 ? '有効' : s === 2 ? '無効' : '不明' }
function statusBadge(s: number) { return s === 1 ? 'badge-green' : 'badge-gray' }

function onImported() {
  showImport.value = false
  fetchContracts()
}

async function fetchContracts() {
  loading.value = true
  try {
    const params: any = { type: 1, page: currentPage.value, size: pageSize }
    if (searchQuery.value) params.keyword = searchQuery.value
    if (statusFilter.value) params.status = statusFilter.value
    const res = await api.get('/contract/paginate', { params })
    const data = res.data
    const items: any[] = data.results ?? data.list ?? data.data ?? []
    contracts.value = items.map((c: any) => ({
      id:            c.id,
      name:          c.name,
      status:        c.status,
      directoryId:   c.directory?.id ?? 0,
      clientName:    c.client?.corporateName ?? c.client?.name ?? c.clientName,
      directoryName: c.directory?.name ?? c.directoryName,
      createdAt:     c.createdAt ?? c.created_at ?? '',
    }))
    total.value = data.page_total ?? data.count ?? data.total ?? items.length
  } finally {
    loading.value = false
  }
}

function goPage(p: number) { currentPage.value = p; fetchContracts() }
function doSearch() { currentPage.value = 1; fetchContracts() }
function clearFilters() { searchQuery.value = ''; statusFilter.value = ''; doSearch() }

onMounted(fetchContracts)
</script>

<style scoped>
.contract-row { cursor: pointer; }

/* ツールバー */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* 取り込みボタン */
.btn-import {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(99,102,241,0.35);
  transition: opacity 0.15s, transform 0.15s;
}
.btn-import:hover { opacity: 0.9; transform: translateY(-1px); }
</style>
