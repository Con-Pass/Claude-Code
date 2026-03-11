<template>
  <div class="container py-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
      <div>
        <h2 class="fw-bold mb-1">コンプライアンスダッシュボード</h2>
        <p class="text-muted mb-0">契約ポートフォリオの健全性を一目で把握</p>
      </div>
      <button class="btn btn-outline-primary" :disabled="rescanning" @click="rescan">
        <span v-if="rescanning" class="spinner-border spinner-border-sm me-1"></span>
        再スキャン
      </button>
    </div>

    <!-- ローディング -->
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">読み込み中...</span>
      </div>
    </div>

    <div v-else>
      <!-- スコアサマリーカード -->
      <div class="row g-3 mb-4">
        <div class="col-md-3">
          <div class="card text-center border-success">
            <div class="card-body">
              <h3 class="text-success fw-bold">{{ summary.high_count }}</h3>
              <small class="text-muted">高スコア（80+）</small>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card text-center border-info">
            <div class="card-body">
              <h3 class="text-info fw-bold">{{ summary.medium_count }}</h3>
              <small class="text-muted">中スコア（60-79）</small>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card text-center border-warning">
            <div class="card-body">
              <h3 class="text-warning fw-bold">{{ summary.low_count }}</h3>
              <small class="text-muted">低スコア（40-59）</small>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card text-center border-danger">
            <div class="card-body">
              <h3 class="text-danger fw-bold">{{ summary.critical_count }}</h3>
              <small class="text-muted">危険（40未満）</small>
            </div>
          </div>
        </div>
      </div>

      <div class="row g-4 mb-4">
        <!-- スコア分布グラフ -->
        <div class="col-md-6">
          <div class="card h-100">
            <div class="card-header bg-light">
              <h6 class="mb-0">スコア分布</h6>
            </div>
            <div class="card-body">
              <div class="score-distribution">
                <div
                  v-for="bar in scoreDistribution"
                  :key="bar.label"
                  class="d-flex align-items-center mb-2"
                >
                  <span class="score-label me-2" style="width: 60px;">{{ bar.label }}</span>
                  <div class="flex-grow-1">
                    <div class="progress" style="height: 24px;">
                      <div
                        class="progress-bar"
                        :class="bar.colorClass"
                        role="progressbar"
                        :style="{ width: bar.percentage + '%' }"
                      >
                        {{ bar.count }}件
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ConPassスコアレーダー（テキスト表現） -->
        <div class="col-md-6">
          <div class="card h-100">
            <div class="card-header bg-light">
              <h6 class="mb-0">ConPassスコア内訳（平均）</h6>
            </div>
            <div class="card-body">
              <div v-for="axis in radarAxes" :key="axis.name" class="mb-3">
                <div class="d-flex justify-content-between mb-1">
                  <span>{{ axis.name }}</span>
                  <span class="fw-bold">{{ axis.score }}/100</span>
                </div>
                <div class="progress" style="height: 10px;">
                  <div
                    class="progress-bar"
                    :class="axisColor(axis.score)"
                    role="progressbar"
                    :style="{ width: axis.score + '%' }"
                  ></div>
                </div>
              </div>
              <div class="text-center mt-3 pt-3 border-top">
                <span class="text-muted">総合スコア: </span>
                <span class="fs-3 fw-bold" :class="overallScoreColor">{{ summary.average_score }}</span>
                <span class="text-muted">/100</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 要注意契約一覧 -->
      <div class="card mb-4">
        <div class="card-header bg-light d-flex justify-content-between align-items-center">
          <h6 class="mb-0">要注意契約（スコア60以下）</h6>
          <span class="badge bg-danger">{{ attentionContracts.length }}件</span>
        </div>
        <div class="card-body p-0">
          <div v-if="attentionContracts.length === 0" class="text-center py-4 text-muted">
            要注意契約はありません
          </div>
          <table v-else class="table table-hover mb-0">
            <thead class="table-light">
              <tr>
                <th>契約名</th>
                <th>取引先</th>
                <th>スコア</th>
                <th>主な問題</th>
                <th>期限</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="contract in attentionContracts" :key="contract.id">
                <td>{{ contract.name }}</td>
                <td>{{ contract.counterparty }}</td>
                <td>
                  <span class="badge" :class="scoreBadge(contract.score)">{{ contract.score }}</span>
                </td>
                <td><small>{{ contract.issue }}</small></td>
                <td>{{ contract.expiry_date }}</td>
                <td>
                  <router-link :to="'/contract/' + contract.id" class="btn btn-outline-primary btn-sm">
                    詳細
                  </router-link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 最近の法令改正影響 -->
      <div class="card">
        <div class="card-header bg-light">
          <h6 class="mb-0">最近の法令改正影響</h6>
        </div>
        <div class="card-body p-0">
          <div v-if="legalUpdates.length === 0" class="text-center py-4 text-muted">
            直近の法令改正影響はありません
          </div>
          <table v-else class="table table-hover mb-0">
            <thead class="table-light">
              <tr>
                <th>法令名</th>
                <th>改正日</th>
                <th>影響契約数</th>
                <th>重要度</th>
                <th>対応状況</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="update in legalUpdates" :key="update.id">
                <td>{{ update.law_name }}</td>
                <td>{{ update.effective_date }}</td>
                <td>{{ update.affected_count }}件</td>
                <td>
                  <span :class="severityBadge(update.severity)">{{ update.severity }}</span>
                </td>
                <td>
                  <span :class="statusBadge(update.status)">{{ update.status_label }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../services/api'

export default {
  name: 'ComplianceDashboard',
  data() {
    return {
      loading: false,
      rescanning: false,
      summary: {
        high_count: 0,
        medium_count: 0,
        low_count: 0,
        critical_count: 0,
        average_score: 0,
        total_contracts: 0
      },
      radarAxes: [
        { name: '期限管理', score: 0 },
        { name: '法令適合性', score: 0 },
        { name: 'ギャップ充足', score: 0 },
        { name: 'メタデータ品質', score: 0 },
        { name: 'リスクレベル', score: 0 }
      ],
      attentionContracts: [],
      legalUpdates: []
    }
  },
  computed: {
    scoreDistribution() {
      const total = this.summary.total_contracts || 1
      return [
        {
          label: '高(80+)',
          count: this.summary.high_count,
          percentage: (this.summary.high_count / total) * 100,
          colorClass: 'bg-success'
        },
        {
          label: '中(60-79)',
          count: this.summary.medium_count,
          percentage: (this.summary.medium_count / total) * 100,
          colorClass: 'bg-info'
        },
        {
          label: '低(40-59)',
          count: this.summary.low_count,
          percentage: (this.summary.low_count / total) * 100,
          colorClass: 'bg-warning'
        },
        {
          label: '危険(<40)',
          count: this.summary.critical_count,
          percentage: (this.summary.critical_count / total) * 100,
          colorClass: 'bg-danger'
        }
      ]
    },
    overallScoreColor() {
      const s = this.summary.average_score
      if (s >= 80) return 'text-success'
      if (s >= 60) return 'text-info'
      if (s >= 40) return 'text-warning'
      return 'text-danger'
    }
  },
  created() {
    this.fetchSummary()
  },
  methods: {
    axisColor(score) {
      if (score >= 80) return 'bg-success'
      if (score >= 60) return 'bg-info'
      if (score >= 40) return 'bg-warning'
      return 'bg-danger'
    },
    scoreBadge(score) {
      if (score >= 80) return 'bg-success'
      if (score >= 60) return 'bg-info'
      if (score >= 40) return 'bg-warning text-dark'
      return 'bg-danger'
    },
    severityBadge(severity) {
      const map = { HIGH: 'badge bg-danger', MEDIUM: 'badge bg-warning text-dark', LOW: 'badge bg-info' }
      return map[severity] || 'badge bg-secondary'
    },
    statusBadge(status) {
      const map = {
        PENDING: 'badge bg-warning text-dark',
        IN_PROGRESS: 'badge bg-info',
        RESOLVED: 'badge bg-success'
      }
      return map[status] || 'badge bg-secondary'
    },
    async fetchSummary() {
      this.loading = true
      try {
        const res = await api.get('/compliance/summary')
        const data = res.data
        this.summary = {
          high_count: data.high_count || 0,
          medium_count: data.medium_count || 0,
          low_count: data.low_count || 0,
          critical_count: data.critical_count || 0,
          average_score: data.average_score || 0,
          total_contracts: data.total_contracts || 0
        }
        if (data.radar_scores) {
          this.radarAxes = [
            { name: '期限管理', score: data.radar_scores.expiry_management || 0 },
            { name: '法令適合性', score: data.radar_scores.legal_compliance || 0 },
            { name: 'ギャップ充足', score: data.radar_scores.gap_coverage || 0 },
            { name: 'メタデータ品質', score: data.radar_scores.metadata_quality || 0 },
            { name: 'リスクレベル', score: data.radar_scores.risk_level || 0 }
          ]
        }
        this.attentionContracts = data.attention_contracts || []
        this.legalUpdates = data.legal_updates || []
      } catch {
        // デモデータで表示
        this.summary = {
          high_count: 12, medium_count: 8, low_count: 5, critical_count: 2,
          average_score: 72, total_contracts: 27
        }
        this.radarAxes = [
          { name: '期限管理', score: 85 },
          { name: '法令適合性', score: 68 },
          { name: 'ギャップ充足', score: 55 },
          { name: 'メタデータ品質', score: 78 },
          { name: 'リスクレベル', score: 74 }
        ]
        this.attentionContracts = [
          { id: 1, name: '業務委託基本契約書', counterparty: '株式会社サンプル', score: 42, issue: '損害賠償条項なし・期限切れ間近', expiry_date: '2026-03-15' },
          { id: 2, name: 'ソフトウェアライセンス契約', counterparty: 'テック株式会社', score: 55, issue: '知的財産権条項が不十分', expiry_date: '2026-04-01' },
          { id: 3, name: '秘密保持契約書', counterparty: '株式会社パートナー', score: 38, issue: '秘密保持期間の定めなし', expiry_date: '2026-02-28' }
        ]
        this.legalUpdates = [
          { id: 1, law_name: '下請法改正', effective_date: '2026-04-01', affected_count: 5, severity: 'HIGH', status: 'PENDING', status_label: '未対応' },
          { id: 2, law_name: '個人情報保護法ガイドライン改訂', effective_date: '2026-06-01', affected_count: 12, severity: 'MEDIUM', status: 'IN_PROGRESS', status_label: '対応中' }
        ]
      } finally {
        this.loading = false
      }
    },
    async rescan() {
      this.rescanning = true
      try {
        await api.post('/compliance/score')
        await this.fetchSummary()
      } catch {
        alert('再スキャン中にエラーが発生しました。')
      } finally {
        this.rescanning = false
      }
    }
  }
}
</script>

<style scoped>
.score-label {
  font-size: 0.85rem;
  text-align: right;
}
</style>
