<template>
  <AppLayout>
    <!-- Playbook 一覧 -->
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px; align-items:start;">
      <div class="card">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px;">
          <h2 style="font-size:14px; font-weight:600;">テナント Playbook</h2>
          <button class="btn btn-primary" @click="showCreateModal = true">＋ 作成</button>
        </div>
        <div v-if="loadingPb" style="color:#718096;">読み込み中...</div>
        <div v-else-if="playbooks.length === 0" style="color:#718096;">Playbook がありません</div>
        <div v-else>
          <div
            v-for="pb in playbooks"
            :key="pb.id"
            style="padding:12px 0; border-bottom:1px solid #f0f4f8; cursor:pointer;"
            @click="selectedPlaybook = pb"
          >
            <div style="font-weight:500;">{{ pb.name }}</div>
            <div style="font-size:12px; color:#718096; margin-top:4px;">
              {{ pb.yourSide === 'VENDOR' ? '提供側' : '受領側' }}
              &nbsp;·&nbsp;
              <span class="badge" :class="pb.isActive ? 'badge-green' : 'badge-gray'">
                {{ pb.isActive ? '有効' : '無効' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 選択された Playbook の詳細 -->
      <div class="card" v-if="selectedPlaybook">
        <h2 style="font-size:14px; font-weight:600; margin-bottom:16px;">{{ selectedPlaybook.name }}</h2>
        <table>
          <tbody>
            <tr>
              <td style="width:110px; color:#718096;">立場</td>
              <td>{{ selectedPlaybook.yourSide === 'VENDOR' ? '提供側 (VENDOR)' : '受領側 (CUSTOMER)' }}</td>
            </tr>
            <tr>
              <td style="color:#718096;">ステータス</td>
              <td>
                <span class="badge" :class="selectedPlaybook.isActive ? 'badge-green' : 'badge-gray'">
                  {{ selectedPlaybook.isActive ? '有効' : '無効' }}
                </span>
              </td>
            </tr>
            <tr v-if="selectedPlaybook.templateName">
              <td style="color:#718096;">テンプレート</td>
              <td>{{ selectedPlaybook.templateName }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card" v-else style="color:#718096;">
        Playbook を選択すると詳細が表示されます
      </div>
    </div>

    <!-- Playbook テンプレート一覧 -->
    <div class="card" style="margin-top:20px;">
      <h2 style="font-size:14px; font-weight:600; margin-bottom:16px;">Playbook テンプレート</h2>
      <div v-if="loadingTmpl" style="color:#718096;">読み込み中...</div>
      <div class="table-wrap" v-else>
        <table>
          <thead>
            <tr>
              <th>テンプレート名</th>
              <th>業種</th>
              <th>説明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in templates" :key="t.id">
              <td style="font-weight:500;">{{ t.name }}</td>
              <td><span class="badge badge-blue">{{ industryLabel(t.industry) }}</span></td>
              <td style="color:#718096;">{{ t.description }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="templates.length === 0" style="color:#718096; padding:16px 0;">テンプレートがありません</div>
      </div>
    </div>

    <!-- 作成モーダル -->
    <div v-if="showCreateModal" style="position:fixed;inset:0;background:rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;z-index:100;">
      <div class="card" style="width:420px;">
        <h3 style="font-size:15px; font-weight:600; margin-bottom:20px;">Playbook 新規作成</h3>
        <div class="form-group">
          <label class="form-label">Playbook 名</label>
          <input class="input" v-model="form.name" placeholder="例: 建設業プレイブック" />
        </div>
        <div class="form-group">
          <label class="form-label">立場</label>
          <select class="input" v-model="form.yourSide">
            <option value="VENDOR">提供側 (VENDOR)</option>
            <option value="CUSTOMER">受領側 (CUSTOMER)</option>
          </select>
        </div>
        <div v-if="createError" class="error-msg">{{ createError }}</div>
        <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:8px;">
          <button class="btn btn-ghost" @click="showCreateModal = false">キャンセル</button>
          <button class="btn btn-primary" @click="createPlaybook" :disabled="creating">
            {{ creating ? '作成中...' : '作成' }}
          </button>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import AppLayout from '../components/AppLayout.vue'
import api from '../api/client'

interface PB { id: number; name: string; yourSide: string; isActive: boolean; templateName?: string }
interface Tmpl { id: number; name: string; industry: string; description: string }

const playbooks       = ref<PB[]>([])
const templates       = ref<Tmpl[]>([])
const selectedPlaybook = ref<PB | null>(null)
const loadingPb   = ref(true)
const loadingTmpl = ref(true)
const showCreateModal = ref(false)
const creating    = ref(false)
const createError = ref('')
const form = ref({ name: '', yourSide: 'VENDOR' })

const INDUSTRY_MAP: Record<string, string> = {
  CONSTRUCTION: '建設',
  IT: 'IT・テクノロジー',
  MANUFACTURING: '製造',
  FINANCE: '金融',
  HEALTHCARE: '医療・ヘルスケア',
  RETAIL: '小売',
  GENERAL: '一般',
}
function industryLabel(code: string) { return INDUSTRY_MAP[code] ?? code }

async function fetchPlaybooks() {
  try {
    const res = await api.get('/playbook/list')
    const items: any[] = res.data.results ?? res.data.list ?? res.data ?? []
    playbooks.value = items.map((p: any) => ({
      id: p.id,
      name: p.name,
      yourSide: p.yourSide ?? p.your_side,
      isActive: p.isActive ?? p.is_active,
      templateName: p.template?.name,
    }))
  } catch {
    playbooks.value = []
  } finally {
    loadingPb.value = false
  }
}

async function fetchTemplates() {
  try {
    const res = await api.get('/playbook/template/list')
    const items: any[] = res.data.results ?? res.data.list ?? res.data ?? []
    templates.value = items.map((t: any) => ({
      id: t.id, name: t.name, industry: t.industry, description: t.description ?? '',
    }))
  } catch {
    templates.value = []
  } finally {
    loadingTmpl.value = false
  }
}

async function createPlaybook() {
  if (!form.value.name.trim()) { createError.value = 'Playbook 名を入力してください'; return }
  creating.value = true
  createError.value = ''
  try {
    await api.post('/playbook', { name: form.value.name, your_side: form.value.yourSide })
    showCreateModal.value = false
    form.value = { name: '', yourSide: 'VENDOR' }
    await fetchPlaybooks()
  } catch (e: any) {
    createError.value = e?.response?.data?.detail ?? '作成に失敗しました'
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  fetchPlaybooks()
  fetchTemplates()
})
</script>
