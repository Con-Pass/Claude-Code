<template>
  <div class="container-fluid py-4">
    <h2 class="mb-4">士業向けダッシュボード</h2>

    <div class="row mb-4">
      <!-- 顧問先一覧テーブル -->
      <div class="col-lg-8">
        <div class="card h-100">
          <div class="card-header fw-bold d-flex justify-content-between align-items-center">
            <span>顧問先一覧</span>
            <div class="d-flex gap-2">
              <input
                v-model="accountSearch"
                type="text"
                class="form-control form-control-sm"
                placeholder="顧問先を検索..."
                style="width: 200px"
              />
              <select v-model="accountSortKey" class="form-select form-select-sm" style="width: 150px">
                <option value="name">名前順</option>
                <option value="score">スコア順</option>
                <option value="actionCount">要対応件数順</option>
                <option value="updatedAt">更新日順</option>
              </select>
            </div>
          </div>
          <div class="card-body p-0">
            <div v-if="accountsLoading" class="text-center py-4">
              <div class="spinner-border spinner-border-sm" role="status"></div>
              <span class="ms-2">読み込み中...</span>
            </div>
            <div v-else class="table-responsive">
              <table class="table table-hover mb-0">
                <thead class="table-light">
                  <tr>
                    <th @click="toggleSort('name')" style="cursor: pointer">
                      顧問先名
                      <span v-if="accountSortKey === 'name'">{{ sortIcon }}</span>
                    </th>
                    <th @click="toggleSort('score')" style="cursor: pointer">
                      ConPassスコア
                      <span v-if="accountSortKey === 'score'">{{ sortIcon }}</span>
                    </th>
                    <th @click="toggleSort('actionCount')" style="cursor: pointer">
                      要対応件数
                      <span v-if="accountSortKey === 'actionCount'">{{ sortIcon }}</span>
                    </th>
                    <th @click="toggleSort('updatedAt')" style="cursor: pointer">
                      最終更新日
                      <span v-if="accountSortKey === 'updatedAt'">{{ sortIcon }}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="account in filteredAccounts"
                    :key="account.id"
                    @click="selectAccount(account)"
                    style="cursor: pointer"
                  >
                    <td>{{ account.name }}</td>
                    <td>
                      <span class="badge" :class="scoreBadgeClass(account.score)">
                        {{ account.score }}
                      </span>
                    </td>
                    <td>
                      <span v-if="account.actionCount > 0" class="badge bg-danger">
                        {{ account.actionCount }}
                      </span>
                      <span v-else class="text-muted">0</span>
                    </td>
                    <td class="text-muted small">{{ formatDate(account.updatedAt) }}</td>
                  </tr>
                  <tr v-if="filteredAccounts.length === 0">
                    <td colspan="4" class="text-center text-muted py-3">該当する顧問先がありません</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- TopicBriefパネル -->
      <div class="col-lg-4">
        <div class="card h-100">
          <div class="card-header fw-bold">Topic Brief 検索</div>
          <div class="card-body">
            <div class="input-group mb-3">
              <input
                v-model="topicQuery"
                type="text"
                class="form-control"
                placeholder="トピックを入力..."
                @keyup.enter="fetchTopicBrief"
              />
              <button
                class="btn btn-primary"
                @click="fetchTopicBrief"
                :disabled="topicLoading || !topicQuery.trim()"
              >
                検索
              </button>
            </div>
            <div v-if="topicLoading" class="text-center py-3">
              <div class="spinner-border spinner-border-sm" role="status"></div>
            </div>
            <div v-else-if="topicBrief">
              <h6>{{ topicBrief.title || topicQuery }}</h6>
              <div class="topic-content" v-html="topicBrief.content"></div>
              <ul v-if="topicBrief.references && topicBrief.references.length" class="list-unstyled mt-2 small">
                <li v-for="(ref, idx) in topicBrief.references" :key="idx">
                  <a :href="ref.url" target="_blank">{{ ref.title }}</a>
                </li>
              </ul>
            </div>
            <p v-else class="text-muted small">トピックを入力して検索してください</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 横断アラート一覧 -->
    <div class="row mb-4">
      <div class="col-12">
        <div class="card">
          <div class="card-header fw-bold d-flex justify-content-between align-items-center">
            <span>全顧問先 横断アラート</span>
            <span class="badge bg-secondary">{{ crossAlerts.length }}件</span>
          </div>
          <div class="card-body p-0">
            <div v-if="crossAlerts.length === 0" class="text-muted p-3">アラートはありません</div>
            <div v-else class="table-responsive">
              <table class="table table-hover mb-0">
                <thead class="table-light">
                  <tr>
                    <th>顧問先</th>
                    <th>アラート内容</th>
                    <th>重要度</th>
                    <th>日時</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="alert in crossAlerts" :key="alert.id">
                    <td>{{ alert.accountName }}</td>
                    <td>{{ alert.message }}</td>
                    <td>
                      <span class="badge" :class="severityClass(alert.severity)">
                        {{ severityLabel(alert.severity) }}
                      </span>
                    </td>
                    <td class="text-muted small text-nowrap">{{ formatDate(alert.evaluatedAt) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- VendorCheckパネル -->
    <div class="row">
      <div class="col-12">
        <div class="card">
          <div class="card-header fw-bold">Vendor Check（取引先チェック）</div>
          <div class="card-body">
            <div class="row">
              <div class="col-md-4">
                <div class="input-group mb-3">
                  <input
                    v-model="vendorName"
                    type="text"
                    class="form-control"
                    placeholder="取引先名を入力..."
                    @keyup.enter="runVendorCheck"
                  />
                  <button
                    class="btn btn-outline-primary"
                    @click="runVendorCheck"
                    :disabled="vendorLoading || !vendorName.trim()"
                  >
                    チェック実行
                  </button>
                </div>
              </div>
            </div>

            <div v-if="vendorLoading" class="text-center py-3">
              <div class="spinner-border spinner-border-sm" role="status"></div>
              <span class="ms-2">チェック中...</span>
            </div>

            <div v-else-if="vendorResult">
              <h6 class="mb-3">{{ vendorResult.vendorName }} - チェック結果</h6>
              <div class="row">
                <div class="col-md-6">
                  <h6 class="small fw-bold">契約状況</h6>
                  <ul class="list-group list-group-flush">
                    <li
                      v-for="(contract, idx) in vendorResult.contracts || []"
                      :key="idx"
                      class="list-group-item small"
                    >
                      {{ contract.type }} - {{ contract.status }}
                      <span v-if="contract.expiryDate" class="text-muted">
                        (期限: {{ contract.expiryDate }})
                      </span>
                    </li>
                    <li
                      v-if="!vendorResult.contracts || vendorResult.contracts.length === 0"
                      class="list-group-item small text-muted"
                    >
                      契約情報なし
                    </li>
                  </ul>
                </div>
                <div class="col-md-6">
                  <h6 class="small fw-bold">Gap Analysis</h6>
                  <ul class="list-group list-group-flush">
                    <li
                      v-for="(gap, idx) in vendorResult.gaps || []"
                      :key="idx"
                      class="list-group-item small"
                    >
                      <span class="badge bg-warning text-dark me-1">不足</span>
                      {{ gap.category }}
                    </li>
                    <li
                      v-if="!vendorResult.gaps || vendorResult.gaps.length === 0"
                      class="list-group-item small text-success"
                    >
                      不足なし
                    </li>
                  </ul>
                </div>
              </div>
              <div v-if="vendorResult.riskSummary" class="mt-3">
                <h6 class="small fw-bold">リスクサマリ</h6>
                <p class="small">{{ vendorResult.riskSummary }}</p>
              </div>
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
  name: 'AdvisorDashboard',

  data() {
    return {
      // 顧問先一覧
      accounts: [],
      accountsLoading: false,
      accountSearch: '',
      accountSortKey: 'name',
      sortAsc: true,

      // 横断アラート
      crossAlerts: [],

      // Topic Brief
      topicQuery: '',
      topicBrief: null,
      topicLoading: false,

      // Vendor Check
      vendorName: '',
      vendorResult: null,
      vendorLoading: false,
    };
  },

  computed: {
    sortIcon() {
      return this.sortAsc ? '\u25B2' : '\u25BC';
    },

    filteredAccounts() {
      let list = [...this.accounts];
      if (this.accountSearch.trim()) {
        const q = this.accountSearch.trim().toLowerCase();
        list = list.filter((a) => a.name.toLowerCase().includes(q));
      }
      list.sort((a, b) => {
        let valA = a[this.accountSortKey];
        let valB = b[this.accountSortKey];
        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();
        if (valA < valB) return this.sortAsc ? -1 : 1;
        if (valA > valB) return this.sortAsc ? 1 : -1;
        return 0;
      });
      return list;
    },
  },

  created() {
    this.fetchAccounts();
    this.fetchCrossAlerts();
  },

  methods: {
    toggleSort(key) {
      if (this.accountSortKey === key) {
        this.sortAsc = !this.sortAsc;
      } else {
        this.accountSortKey = key;
        this.sortAsc = true;
      }
    },

    async fetchAccounts() {
      this.accountsLoading = true;
      try {
        const res = await axios.get('/api/v1/compliance/summary', {
          params: { view: 'advisor' },
        });
        this.accounts = res.data.accounts || [];
      } catch (err) {
        console.error('顧問先一覧の取得に失敗:', err);
      } finally {
        this.accountsLoading = false;
      }
    },

    async fetchCrossAlerts() {
      try {
        const res = await axios.get('/api/v1/tenant/rules/alerts/', {
          params: { cross: true },
        });
        this.crossAlerts = res.data.results || res.data || [];
      } catch (err) {
        console.error('横断アラートの取得に失敗:', err);
      }
    },

    async fetchTopicBrief() {
      if (!this.topicQuery.trim()) return;
      this.topicLoading = true;
      this.topicBrief = null;
      try {
        const res = await axios.get('/api/v1/legal/brief', {
          params: { mode: 'topic', query: this.topicQuery },
        });
        this.topicBrief = res.data;
      } catch (err) {
        console.error('Topic Briefの取得に失敗:', err);
      } finally {
        this.topicLoading = false;
      }
    },

    async runVendorCheck() {
      if (!this.vendorName.trim()) return;
      this.vendorLoading = true;
      this.vendorResult = null;
      try {
        const res = await axios.post('/api/v1/legal/vendor-check', {
          vendor_name: this.vendorName,
        });
        this.vendorResult = res.data;
      } catch (err) {
        console.error('Vendor Checkに失敗:', err);
      } finally {
        this.vendorLoading = false;
      }
    },

    selectAccount(account) {
      this.$router.push({ name: 'Dashboard', query: { accountId: account.id } });
    },

    formatDate(dateStr) {
      if (!dateStr) return '-';
      const d = new Date(dateStr);
      return d.toLocaleDateString('ja-JP');
    },

    scoreBadgeClass(score) {
      if (score >= 80) return 'bg-success';
      if (score >= 60) return 'bg-warning text-dark';
      return 'bg-danger';
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
.topic-content {
  max-height: 300px;
  overflow-y: auto;
  font-size: 0.9rem;
}
</style>
