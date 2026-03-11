<template>
  <div class="container py-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
      <div>
        <h2 class="fw-bold mb-1">業界団体OEMダッシュボード</h2>
        <p class="text-muted mb-0">加盟企業の契約管理状況を一括把握</p>
      </div>
    </div>

    <div class="row g-4">
      <!-- 加盟企業一覧 -->
      <div class="col-md-8">
        <div class="card">
          <div class="card-header bg-light d-flex justify-content-between align-items-center">
            <h5 class="mb-0">加盟企業一覧</h5>
            <span class="badge bg-primary">{{ members.length }}社</span>
          </div>
          <div class="card-body p-0">
            <div v-if="loading" class="text-center py-4">
              <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">読み込み中...</span>
              </div>
            </div>
            <table v-else class="table table-hover mb-0">
              <thead class="table-light">
                <tr>
                  <th @click="sortBy('name')" role="button">
                    企業名
                    <span v-if="sortKey === 'name'">{{ sortDir === 'asc' ? '&#x25B2;' : '&#x25BC;' }}</span>
                  </th>
                  <th @click="sortBy('score')" role="button">
                    ConPassスコア
                    <span v-if="sortKey === 'score'">{{ sortDir === 'asc' ? '&#x25B2;' : '&#x25BC;' }}</span>
                  </th>
                  <th @click="sortBy('action_count')" role="button">
                    要対応件数
                    <span v-if="sortKey === 'action_count'">{{ sortDir === 'asc' ? '&#x25B2;' : '&#x25BC;' }}</span>
                  </th>
                  <th>ステータス</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="member in sortedMembers" :key="member.id">
                  <td>{{ member.name }}</td>
                  <td>
                    <span class="badge" :class="scoreBadge(member.score)">{{ member.score }}</span>
                  </td>
                  <td>
                    <span v-if="member.action_count > 0" class="badge bg-danger">{{ member.action_count }}件</span>
                    <span v-else class="text-success">-</span>
                  </td>
                  <td>
                    <span :class="memberStatusBadge(member.status)">{{ member.status_label }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- PlaybookTemplate作成パネル -->
      <div class="col-md-4">
        <div class="card">
          <div class="card-header bg-light">
            <h5 class="mb-0">テンプレート作成</h5>
          </div>
          <div class="card-body">
            <p class="text-muted small mb-3">加盟企業向けのデフォルトルールを定義します。</p>
            <form @submit.prevent="createTemplate">
              <div class="mb-3">
                <label class="form-label">テンプレート名</label>
                <input v-model="newTemplate.name" type="text" class="form-control" placeholder="例: IT業界標準契約ルール" required>
              </div>
              <div class="mb-3">
                <label class="form-label">業種カテゴリ</label>
                <select v-model="newTemplate.industry" class="form-select" required>
                  <option value="">-- 選択 --</option>
                  <option value="IT">IT・ソフトウェア</option>
                  <option value="CONSTRUCTION">建設業</option>
                  <option value="RETAIL">小売・EC</option>
                  <option value="MANUFACTURING">製造業</option>
                  <option value="PROFESSIONAL">士業・コンサル</option>
                  <option value="OTHER">その他</option>
                </select>
              </div>
              <div class="mb-3">
                <label class="form-label">説明</label>
                <textarea v-model="newTemplate.description" class="form-control" rows="3" placeholder="テンプレートの概要・適用対象"></textarea>
              </div>

              <h6 class="mt-4 mb-3">デフォルトルール定義</h6>
              <div v-for="(rule, idx) in newTemplate.rules" :key="idx" class="border rounded p-3 mb-2">
                <div class="d-flex justify-content-between align-items-center mb-2">
                  <strong class="small">ルール {{ idx + 1 }}</strong>
                  <button type="button" class="btn btn-outline-danger btn-sm" @click="removeRule(idx)">&times;</button>
                </div>
                <div class="mb-2">
                  <select v-model="rule.rule_type" class="form-select form-select-sm">
                    <option value="EXPIRY_ALERT">期限アラート</option>
                    <option value="REQUIRED_CONTRACT">必須契約チェック</option>
                    <option value="AMOUNT_THRESHOLD">金額しきい値</option>
                    <option value="AUTO_RENEWAL">自動更新通知</option>
                    <option value="CLAUSE_CHECK">条項チェック</option>
                  </select>
                </div>
                <div class="mb-2">
                  <input v-model="rule.name" type="text" class="form-control form-control-sm" placeholder="ルール名">
                </div>
                <div>
                  <select v-model="rule.severity" class="form-select form-select-sm">
                    <option value="HIGH">高</option>
                    <option value="MEDIUM">中</option>
                    <option value="LOW">低</option>
                  </select>
                </div>
              </div>
              <button type="button" class="btn btn-outline-secondary btn-sm w-100 mb-3" @click="addRule">
                + ルールを追加
              </button>

              <button type="submit" class="btn btn-primary w-100" :disabled="creatingTemplate">
                <span v-if="creatingTemplate" class="spinner-border spinner-border-sm me-1"></span>
                テンプレートを作成
              </button>
            </form>

            <div v-if="templateCreated" class="alert alert-success mt-3 mb-0">
              テンプレートを作成しました。
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../services/api'

export default {
  name: 'OEMDashboard',
  data() {
    return {
      loading: false,
      members: [],
      sortKey: 'score',
      sortDir: 'asc',
      newTemplate: {
        name: '',
        industry: '',
        description: '',
        rules: [
          { rule_type: 'EXPIRY_ALERT', name: '', severity: 'HIGH' }
        ]
      },
      creatingTemplate: false,
      templateCreated: false
    }
  },
  computed: {
    sortedMembers() {
      const sorted = [...this.members]
      sorted.sort((a, b) => {
        let aVal = a[this.sortKey]
        let bVal = b[this.sortKey]
        if (typeof aVal === 'string') aVal = aVal.toLowerCase()
        if (typeof bVal === 'string') bVal = bVal.toLowerCase()
        if (aVal < bVal) return this.sortDir === 'asc' ? -1 : 1
        if (aVal > bVal) return this.sortDir === 'asc' ? 1 : -1
        return 0
      })
      return sorted
    }
  },
  created() {
    this.fetchMembers()
  },
  methods: {
    scoreBadge(score) {
      if (score >= 80) return 'bg-success'
      if (score >= 60) return 'bg-info'
      if (score >= 40) return 'bg-warning text-dark'
      return 'bg-danger'
    },
    memberStatusBadge(status) {
      const map = {
        ACTIVE: 'badge bg-success',
        WARNING: 'badge bg-warning text-dark',
        SUSPENDED: 'badge bg-danger'
      }
      return map[status] || 'badge bg-secondary'
    },
    sortBy(key) {
      if (this.sortKey === key) {
        this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc'
      } else {
        this.sortKey = key
        this.sortDir = 'asc'
      }
    },
    addRule() {
      this.newTemplate.rules.push({ rule_type: 'EXPIRY_ALERT', name: '', severity: 'MEDIUM' })
    },
    removeRule(idx) {
      this.newTemplate.rules.splice(idx, 1)
    },
    async fetchMembers() {
      this.loading = true
      try {
        const res = await api.get('/oem/members/')
        this.members = res.data.results || res.data
      } catch {
        this.members = [
          { id: 1, name: '株式会社サンプル商事', score: 85, action_count: 0, status: 'ACTIVE', status_label: '正常' },
          { id: 2, name: '有限会社テスト工業', score: 62, action_count: 3, status: 'WARNING', status_label: '要注意' },
          { id: 3, name: '合同会社デモサービス', score: 45, action_count: 7, status: 'WARNING', status_label: '要注意' },
          { id: 4, name: '株式会社プロトタイプ', score: 91, action_count: 0, status: 'ACTIVE', status_label: '正常' },
          { id: 5, name: '有限会社ビルド建設', score: 38, action_count: 12, status: 'SUSPENDED', status_label: '対応必須' }
        ]
      } finally {
        this.loading = false
      }
    },
    async createTemplate() {
      this.creatingTemplate = true
      this.templateCreated = false
      try {
        await api.post('/oem/playbook-template/', this.newTemplate)
        this.templateCreated = true
        this.newTemplate = {
          name: '',
          industry: '',
          description: '',
          rules: [{ rule_type: 'EXPIRY_ALERT', name: '', severity: 'HIGH' }]
        }
      } catch {
        alert('テンプレート作成中にエラーが発生しました。')
      } finally {
        this.creatingTemplate = false
      }
    }
  }
}
</script>
