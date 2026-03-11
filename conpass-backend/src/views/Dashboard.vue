<template>
  <div class="container-fluid py-4">
    <h2 class="mb-4">ConPass ダッシュボード</h2>

    <!-- 上段: スコアゲージ + Gap Analysis -->
    <div class="row mb-4">
      <!-- ConPassスコアゲージ -->
      <div class="col-md-4">
        <div class="card h-100">
          <div class="card-header fw-bold">ConPass スコア</div>
          <div class="card-body text-center">
            <div class="score-gauge mx-auto" :class="scoreColorClass">
              <span class="score-value">{{ complianceScore }}</span>
              <span class="score-label">/ 100</span>
            </div>
            <p class="mt-2 mb-0" :class="'text-' + scoreColor">{{ scoreLabel }}</p>
          </div>
        </div>
      </div>

      <!-- Gap Analysisパネル -->
      <div class="col-md-4">
        <div class="card h-100">
          <div class="card-header fw-bold">Gap Analysis</div>
          <div class="card-body">
            <p v-if="gaps.length === 0" class="text-muted">不足している契約種別はありません</p>
            <ul class="list-group list-group-flush" v-else>
              <li
                v-for="gap in gaps"
                :key="gap.category"
                class="list-group-item d-flex justify-content-between align-items-center"
              >
                <span>{{ gap.category }}</span>
                <button class="btn btn-sm btn-primary" @click="createContract(gap.category)">
                  作成する
                </button>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Daily Brief -->
      <div class="col-md-4">
        <div class="card h-100">
          <div class="card-header fw-bold">Daily Brief</div>
          <div class="card-body">
            <div v-if="dailyBriefLoading" class="text-center py-3">
              <div class="spinner-border spinner-border-sm" role="status"></div>
              <span class="ms-2">読み込み中...</span>
            </div>
            <div v-else-if="dailyBrief">
              <p class="mb-1"><strong>{{ dailyBrief.title || '本日のブリーフ' }}</strong></p>
              <p class="text-muted small mb-2">{{ dailyBrief.date }}</p>
              <div class="brief-content" v-html="dailyBrief.content"></div>
              <ul v-if="dailyBrief.items && dailyBrief.items.length" class="list-unstyled mt-2">
                <li v-for="(item, idx) in dailyBrief.items" :key="idx" class="mb-1">
                  <span class="badge bg-info me-1">{{ item.type }}</span>
                  {{ item.summary }}
                </li>
              </ul>
            </div>
            <p v-else class="text-muted">ブリーフ情報がありません</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 中段: アラートタイムライン -->
    <div class="row mb-4">
      <div class="col-12">
        <div class="card">
          <div class="card-header fw-bold">期限アラート タイムライン</div>
          <div class="card-body">
            <div v-if="expiryAlerts.length === 0" class="text-muted">期限が近い契約はありません</div>
            <div v-else class="table-responsive">
              <table class="table table-hover mb-0">
                <thead>
                  <tr>
                    <th>契約名</th>
                    <th>相手方</th>
                    <th>期限日</th>
                    <th>残日数</th>
                    <th>ステータス</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="alert in expiryAlerts" :key="alert.id">
                    <td>{{ alert.contractName }}</td>
                    <td>{{ alert.counterparty }}</td>
                    <td>{{ alert.expiryDate }}</td>
                    <td>
                      <span :class="expiryBadgeClass(alert.daysRemaining)">
                        {{ alert.daysRemaining }}日
                      </span>
                    </td>
                    <td>
                      <span :class="'badge bg-' + expiryColor(alert.daysRemaining)">
                        {{ expiryLabel(alert.daysRemaining) }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 下段: ルール評価アラート一覧 -->
    <div class="row">
      <div class="col-12">
        <div class="card">
          <div class="card-header fw-bold d-flex justify-content-between align-items-center">
            <span>アラート一覧</span>
            <span class="badge bg-secondary">{{ ruleAlerts.length }}件</span>
          </div>
          <div class="card-body">
            <div v-if="alertsLoading" class="text-center py-3">
              <div class="spinner-border spinner-border-sm" role="status"></div>
              <span class="ms-2">読み込み中...</span>
            </div>
            <div v-else-if="ruleAlerts.length === 0" class="text-muted">アラートはありません</div>
            <div v-else class="table-responsive">
              <table class="table table-hover mb-0">
                <thead>
                  <tr>
                    <th>日時</th>
                    <th>ルール</th>
                    <th>結果</th>
                    <th>重要度</th>
                    <th>詳細</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="alert in ruleAlerts" :key="alert.id">
                    <td class="text-nowrap">{{ formatDate(alert.evaluatedAt) }}</td>
                    <td>{{ alert.ruleName }}</td>
                    <td>
                      <span
                        class="badge"
                        :class="alert.result === 'FAIL' ? 'bg-danger' : 'bg-warning text-dark'"
                      >
                        {{ alert.result }}
                      </span>
                    </td>
                    <td>
                      <span class="badge" :class="severityClass(alert.severity)">
                        {{ severityLabel(alert.severity) }}
                      </span>
                    </td>
                    <td class="small">{{ alert.message }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'Dashboard',

  data() {
    return {
      // コンプライアンスサマリ
      complianceScore: 0,
      gaps: [],
      expiryAlerts: [],

      // Daily Brief
      dailyBrief: null,
      dailyBriefLoading: false,

      // ルール評価アラート
      ruleAlerts: [],
      alertsLoading: false,
    };
  },

  computed: {
    scoreColor() {
      if (this.complianceScore >= 80) return 'success';
      if (this.complianceScore >= 60) return 'warning';
      return 'danger';
    },
    scoreColorClass() {
      return 'score-' + this.scoreColor;
    },
    scoreLabel() {
      if (this.complianceScore >= 80) return '良好';
      if (this.complianceScore >= 60) return '要改善';
      return '要対応';
    },
  },

  created() {
    this.fetchComplianceSummary();
    this.fetchDailyBrief();
    this.fetchAlerts();
  },

  methods: {
    async fetchComplianceSummary() {
      try {
        const res = await axios.get('/api/v1/compliance/summary');
        const data = res.data;
        this.complianceScore = data.score || 0;
        this.gaps = data.gaps || [];
        this.expiryAlerts = data.expiryAlerts || [];
      } catch (err) {
        console.error('コンプライアンスサマリの取得に失敗:', err);
      }
    },

    async fetchDailyBrief() {
      this.dailyBriefLoading = true;
      try {
        const res = await axios.get('/api/v1/legal/brief', {
          params: { mode: 'daily' },
        });
        this.dailyBrief = res.data;
      } catch (err) {
        console.error('Daily Briefの取得に失敗:', err);
      } finally {
        this.dailyBriefLoading = false;
      }
    },

    async fetchAlerts() {
      this.alertsLoading = true;
      try {
        const res = await axios.get('/api/v1/tenant/rules/alerts/');
        this.ruleAlerts = (res.data.results || res.data || []).filter(
          (a) => a.result === 'WARN' || a.result === 'FAIL'
        );
      } catch (err) {
        console.error('アラートの取得に失敗:', err);
      } finally {
        this.alertsLoading = false;
      }
    },

    createContract(category) {
      this.$router.push({ name: 'ContractCreate', query: { category } });
    },

    formatDate(dateStr) {
      if (!dateStr) return '-';
      const d = new Date(dateStr);
      return d.toLocaleDateString('ja-JP') + ' ' + d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
    },

    expiryColor(days) {
      if (days <= 30) return 'danger';
      if (days <= 60) return 'warning';
      return 'info';
    },

    expiryBadgeClass(days) {
      if (days <= 30) return 'text-danger fw-bold';
      if (days <= 60) return 'text-warning fw-bold';
      return 'text-info';
    },

    expiryLabel(days) {
      if (days <= 30) return '緊急';
      if (days <= 60) return '注意';
      return '確認';
    },

    severityClass(severity) {
      const map = { CRITICAL: 'bg-danger', WARNING: 'bg-warning text-dark', INFO: 'bg-info' };
      return map[severity] || 'bg-secondary';
    },

    severityLabel(severity) {
      const map = { CRITICAL: '緊急', WARNING: '警告', INFO: '情報' };
      return map[severity] || severity;
    },
  },
};
</script>

<style scoped>
.score-gauge {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 6px solid #dee2e6;
}
.score-gauge.score-success {
  border-color: #198754;
  background-color: #d1e7dd;
}
.score-gauge.score-warning {
  border-color: #ffc107;
  background-color: #fff3cd;
}
.score-gauge.score-danger {
  border-color: #dc3545;
  background-color: #f8d7da;
}
.score-value {
  font-size: 2.5rem;
  font-weight: bold;
  line-height: 1;
}
.score-label {
  font-size: 0.9rem;
  color: #6c757d;
}
.brief-content {
  max-height: 200px;
  overflow-y: auto;
  font-size: 0.9rem;
}
</style>
