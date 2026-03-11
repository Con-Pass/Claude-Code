<template>
  <AppLayout>
    <div class="stats-grid">
      <div class="stat-card" v-for="stat in stats" :key="stat.label">
        <div class="stat-label">{{ stat.label }}</div>
        <div class="stat-value">{{ stat.value }}</div>
      </div>
    </div>

    <div class="card">
      <h2 style="font-size:14px; font-weight:600; margin-bottom:16px;">最近の契約書</h2>
      <div v-if="loading" style="color:#718096;">読み込み中...</div>
      <div v-else-if="recentContracts.length === 0" style="color:#718096;">データがありません</div>
      <div class="table-wrap" v-else>
        <table>
          <thead>
            <tr>
              <th>契約書名</th>
              <th>取引先</th>
              <th>ステータス</th>
              <th>作成日</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in recentContracts" :key="c.id">
              <td>{{ c.name }}</td>
              <td>{{ c.clientName ?? '-' }}</td>
              <td><span class="badge badge-green">有効</span></td>
              <td>{{ formatDate(c.createdAt) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import AppLayout from '../components/AppLayout.vue'
import api from '../api/client'

interface ContractRow {
  id: number
  name: string
  clientName?: string
  createdAt: string
}

const loading = ref(true)
const recentContracts = ref<ContractRow[]>([])
const stats = ref([
  { label: '契約書（総数）', value: '-' },
  { label: '有効', value: '-' },
  { label: '期限切れ間近', value: '-' },
])

function formatDate(d: string) {
  return d ? d.slice(0, 10) : '-'
}

onMounted(async () => {
  try {
    const res = await api.get('/contract/paginate', { params: { type: 1, page: 1, size: 5 } })
    const data = res.data
    // DRF camelCase レスポンス対応
    const items: any[] = data.results ?? data.list ?? data.data ?? []
    recentContracts.value = items.map((c: any) => ({
      id: c.id,
      name: c.name,
      clientName: c.client?.name ?? c.clientName,
      createdAt: c.createdAt ?? c.created_at ?? '',
    }))
    const total = data.count ?? data.total ?? items.length
    if (stats.value[0]) stats.value[0].value = String(total)
    if (stats.value[1]) stats.value[1].value = String(total)
    if (stats.value[2]) stats.value[2].value = '0'
  } catch (e) {
    // 認証エラー等はルーターガードが処理
  } finally {
    loading.value = false
  }
})
</script>
