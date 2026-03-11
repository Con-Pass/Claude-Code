<template>
  <div class="container py-4">
    <div class="row justify-content-center">
      <div class="col-md-8">
        <!-- ヘッダー -->
        <div class="text-center mb-4">
          <h2 class="fw-bold">ようこそ、STプランへ</h2>
          <p class="text-muted">3つのステップで、契約管理の力を解放しましょう。</p>
        </div>

        <!-- プログレスバー -->
        <div class="d-flex justify-content-between mb-4 position-relative">
          <div v-for="(s, idx) in steps" :key="idx" class="text-center flex-fill">
            <div
              class="rounded-circle d-inline-flex align-items-center justify-content-center mb-2"
              :class="stepCircleClass(idx)"
              style="width: 40px; height: 40px;"
            >
              <span v-if="idx < currentStep" class="text-white">&#x2713;</span>
              <span v-else>{{ idx + 1 }}</span>
            </div>
            <div class="small" :class="{ 'fw-bold': idx === currentStep }">{{ s.label }}</div>
          </div>
        </div>

        <!-- ステップ1: 業種選択 -->
        <div v-if="currentStep === 0" class="card">
          <div class="card-header bg-light">
            <h5 class="mb-0">ステップ 1: 業種を選択してください</h5>
          </div>
          <div class="card-body">
            <p class="text-muted mb-3">業種に合わせた契約管理テンプレートを自動適用します。</p>
            <div v-if="loadingTemplates" class="text-center py-4">
              <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">読み込み中...</span>
              </div>
            </div>
            <div v-else class="row g-3">
              <div v-for="tpl in templates" :key="tpl.id" class="col-md-6">
                <div
                  class="card cursor-pointer h-100"
                  :class="{ 'border-warning border-2': selectedTemplate === tpl.id }"
                  @click="selectedTemplate = tpl.id"
                  role="button"
                >
                  <div class="card-body">
                    <h6 class="card-title">{{ tpl.name }}</h6>
                    <p class="card-text small text-muted">{{ tpl.description }}</p>
                    <span v-if="tpl.clause_count" class="badge bg-secondary">{{ tpl.clause_count }}条項</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="mt-4 text-end">
              <button
                class="btn btn-warning"
                :disabled="!selectedTemplate || applyingTemplate"
                @click="applyTemplate"
              >
                <span v-if="applyingTemplate" class="spinner-border spinner-border-sm me-1"></span>
                テンプレートを適用して次へ
              </button>
            </div>
          </div>
        </div>

        <!-- ステップ2: ルール確認・有効化 -->
        <div v-if="currentStep === 1" class="card">
          <div class="card-header bg-light">
            <h5 class="mb-0">ステップ 2: 推奨ルールを確認・有効化</h5>
          </div>
          <div class="card-body">
            <p class="text-muted mb-3">選択した業種に推奨されるルールです。必要に応じてオン/オフを切り替えてください。</p>
            <div v-if="loadingRules" class="text-center py-4">
              <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">読み込み中...</span>
              </div>
            </div>
            <table v-else class="table table-hover">
              <thead>
                <tr>
                  <th>有効</th>
                  <th>ルール名</th>
                  <th>種別</th>
                  <th>重要度</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="rule in rules" :key="rule.id">
                  <td>
                    <div class="form-check form-switch">
                      <input
                        class="form-check-input"
                        type="checkbox"
                        v-model="rule.is_active"
                        :id="'rule-' + rule.id"
                      >
                    </div>
                  </td>
                  <td>
                    <label :for="'rule-' + rule.id" class="form-check-label">{{ rule.name }}</label>
                  </td>
                  <td><span class="badge bg-secondary">{{ rule.rule_type }}</span></td>
                  <td>
                    <span :class="severityBadge(rule.severity)">{{ rule.severity }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div class="mt-4 d-flex justify-content-between">
              <button class="btn btn-outline-secondary" @click="currentStep = 0">戻る</button>
              <button class="btn btn-warning" :disabled="savingRules" @click="saveRules">
                <span v-if="savingRules" class="spinner-border spinner-border-sm me-1"></span>
                ルールを保存して次へ
              </button>
            </div>
          </div>
        </div>

        <!-- ステップ3: 最初のレポート生成 -->
        <div v-if="currentStep === 2" class="card">
          <div class="card-header bg-light">
            <h5 class="mb-0">ステップ 3: 最初のレポートを生成</h5>
          </div>
          <div class="card-body">
            <p class="text-muted mb-3">
              設定が完了しました。最初のデイリーブリーフを生成して、ConPassの実力を体感してください。
            </p>

            <div v-if="!briefGenerated && !generatingBrief" class="text-center py-4">
              <button class="btn btn-warning btn-lg" @click="generateBrief">
                デイリーブリーフを生成する
              </button>
            </div>

            <div v-if="generatingBrief" class="text-center py-4">
              <div class="spinner-border text-warning mb-3" role="status"></div>
              <p class="text-muted">AIがあなたの契約データを分析中です...</p>
            </div>

            <div v-if="briefGenerated" class="mt-3">
              <div class="card bg-light">
                <div class="card-header">
                  <strong>デイリーブリーフ</strong>
                  <small class="text-muted ms-2">{{ briefData.generated_at }}</small>
                </div>
                <div class="card-body">
                  <div v-if="briefData.summary" class="mb-3">
                    <h6>サマリー</h6>
                    <p>{{ briefData.summary }}</p>
                  </div>
                  <div v-if="briefData.alerts && briefData.alerts.length" class="mb-3">
                    <h6>アラート</h6>
                    <ul class="list-group list-group-flush">
                      <li v-for="(alert, idx) in briefData.alerts" :key="idx" class="list-group-item">
                        <span :class="alertBadge(alert.level)">{{ alert.level }}</span>
                        {{ alert.message }}
                      </li>
                    </ul>
                  </div>
                  <div v-if="briefData.expiring_contracts && briefData.expiring_contracts.length">
                    <h6>期限間近の契約</h6>
                    <ul class="list-group list-group-flush">
                      <li v-for="(c, idx) in briefData.expiring_contracts" :key="idx" class="list-group-item d-flex justify-content-between">
                        <span>{{ c.name }}</span>
                        <span class="badge bg-danger">{{ c.days_until_expiry }}日後</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>

              <div class="mt-4 text-center">
                <p class="fw-bold text-success mb-2">セットアップ完了!</p>
                <p class="text-muted">契約は、力だ。ConPassで、その力を最大限に活用しましょう。</p>
                <router-link to="/dashboard" class="btn btn-primary btn-lg">ダッシュボードへ</router-link>
              </div>
            </div>

            <div v-if="!briefGenerated" class="mt-4 d-flex justify-content-between">
              <button class="btn btn-outline-secondary" @click="currentStep = 1">戻る</button>
              <router-link to="/dashboard" class="btn btn-outline-primary">スキップしてダッシュボードへ</router-link>
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
  name: 'OnboardingWizard',
  data() {
    return {
      currentStep: 0,
      steps: [
        { label: '業種選択' },
        { label: 'ルール設定' },
        { label: 'レポート生成' }
      ],
      // ステップ1
      templates: [],
      selectedTemplate: null,
      loadingTemplates: false,
      applyingTemplate: false,
      // ステップ2
      rules: [],
      loadingRules: false,
      savingRules: false,
      // ステップ3
      generatingBrief: false,
      briefGenerated: false,
      briefData: {}
    }
  },
  created() {
    this.fetchTemplates()
  },
  methods: {
    stepCircleClass(idx) {
      if (idx < this.currentStep) return 'bg-success text-white'
      if (idx === this.currentStep) return 'bg-warning text-dark'
      return 'bg-light text-muted border'
    },
    severityBadge(severity) {
      const map = { HIGH: 'badge bg-danger', MEDIUM: 'badge bg-warning text-dark', LOW: 'badge bg-info' }
      return map[severity] || 'badge bg-secondary'
    },
    alertBadge(level) {
      const map = { CRITICAL: 'badge bg-danger me-2', WARNING: 'badge bg-warning text-dark me-2', INFO: 'badge bg-info me-2' }
      return map[level] || 'badge bg-secondary me-2'
    },
    async fetchTemplates() {
      this.loadingTemplates = true
      try {
        const res = await api.get('/tenant/playbook/templates/')
        this.templates = res.data.results || res.data
      } catch {
        this.templates = [
          { id: 'it', name: 'IT・SaaS', description: 'SaaS契約・ライセンス契約に特化したテンプレート', clause_count: 12 },
          { id: 'construction', name: '建設業', description: '建設工事請負契約・下請法対応テンプレート', clause_count: 10 },
          { id: 'retail', name: '小売・EC', description: '取引基本契約・物流契約対応テンプレート', clause_count: 8 },
          { id: 'professional', name: '士業・コンサル', description: '顧問契約・業務委託対応テンプレート', clause_count: 11 },
          { id: 'manufacturing', name: '製造業', description: '取引基本契約・品質保証対応テンプレート', clause_count: 9 },
          { id: 'general', name: '一般（汎用）', description: '業種を問わない汎用テンプレート', clause_count: 12 }
        ]
      } finally {
        this.loadingTemplates = false
      }
    },
    async applyTemplate() {
      this.applyingTemplate = true
      try {
        await api.post('/tenant/playbook/apply-template/', { template_id: this.selectedTemplate })
        await this.fetchRules()
        this.currentStep = 1
      } catch {
        await this.fetchRules()
        this.currentStep = 1
      } finally {
        this.applyingTemplate = false
      }
    },
    async fetchRules() {
      this.loadingRules = true
      try {
        const res = await api.get('/tenant/rules/')
        this.rules = (res.data.results || res.data).map(r => ({ ...r, is_active: r.is_active !== false }))
      } catch {
        this.rules = [
          { id: 1, name: '契約期限アラート（90日前）', rule_type: 'EXPIRY_ALERT', severity: 'HIGH', is_active: true },
          { id: 2, name: '契約期限アラート（60日前）', rule_type: 'EXPIRY_ALERT', severity: 'MEDIUM', is_active: true },
          { id: 3, name: '契約期限アラート（30日前）', rule_type: 'EXPIRY_ALERT', severity: 'HIGH', is_active: true },
          { id: 4, name: '秘密保持契約の必須チェック', rule_type: 'REQUIRED_CONTRACT', severity: 'HIGH', is_active: true },
          { id: 5, name: '取引金額しきい値アラート', rule_type: 'AMOUNT_THRESHOLD', severity: 'MEDIUM', is_active: false },
          { id: 6, name: '自動更新契約の事前通知', rule_type: 'AUTO_RENEWAL', severity: 'MEDIUM', is_active: true }
        ]
      } finally {
        this.loadingRules = false
      }
    },
    async saveRules() {
      this.savingRules = true
      try {
        await api.put('/tenant/rules/bulk-update/', {
          rules: this.rules.map(r => ({ id: r.id, is_active: r.is_active }))
        })
      } catch {
        // フォールバック: 次のステップへ進む
      } finally {
        this.savingRules = false
        this.currentStep = 2
      }
    },
    async generateBrief() {
      this.generatingBrief = true
      try {
        const res = await api.post('/legal-command/brief/', { type: 'daily' })
        this.briefData = res.data
        this.briefGenerated = true
      } catch {
        this.briefData = {
          generated_at: new Date().toLocaleString('ja-JP'),
          summary: '現在登録されている契約はまだありません。契約書をアップロードすると、AIが自動で分析を開始します。',
          alerts: [],
          expiring_contracts: []
        }
        this.briefGenerated = true
      } finally {
        this.generatingBrief = false
      }
    }
  }
}
</script>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}
.cursor-pointer:hover {
  background-color: #f8f9fa;
}
</style>
