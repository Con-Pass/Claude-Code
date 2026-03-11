<template>
  <div class="container-fluid py-4">
    <h2 class="mb-4">ルール管理</h2>

    <!-- ルール一覧 -->
    <div class="card mb-4">
      <div class="card-header fw-bold d-flex justify-content-between align-items-center">
        <span>テナントルール一覧</span>
        <div class="d-flex gap-2">
          <!-- フィルタ -->
          <select v-model="filterRuleType" class="form-select form-select-sm" style="width: 160px">
            <option value="">全ルール種別</option>
            <option v-for="rt in ruleTypeOptions" :key="rt.value" :value="rt.value">
              {{ rt.label }}
            </option>
          </select>
          <select v-model="filterSeverity" class="form-select form-select-sm" style="width: 120px">
            <option value="">全重要度</option>
            <option value="INFO">情報</option>
            <option value="WARNING">警告</option>
            <option value="CRITICAL">緊急</option>
          </select>
          <select v-model="filterActive" class="form-select form-select-sm" style="width: 120px">
            <option value="">全状態</option>
            <option value="true">有効</option>
            <option value="false">無効</option>
          </select>
          <button class="btn btn-sm btn-primary" @click="openAddModal">
            ルール追加
          </button>
        </div>
      </div>
      <div class="card-body p-0">
        <div v-if="rulesLoading" class="text-center py-4">
          <div class="spinner-border spinner-border-sm" role="status"></div>
          <span class="ms-2">読み込み中...</span>
        </div>
        <div v-else class="table-responsive">
          <table class="table table-hover mb-0">
            <thead class="table-light">
              <tr>
                <th>ルール名</th>
                <th>種別</th>
                <th>重要度</th>
                <th>状態</th>
                <th>条件</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rule in filteredRules" :key="rule.id">
                <td>{{ rule.name || rule.ruleName || '-' }}</td>
                <td>
                  <span class="badge bg-secondary">{{ ruleTypeLabel(rule.ruleType) }}</span>
                </td>
                <td>
                  <span class="badge" :class="severityClass(rule.severity)">
                    {{ severityLabel(rule.severity) }}
                  </span>
                </td>
                <td>
                  <span
                    class="badge"
                    :class="rule.isActive ? 'bg-success' : 'bg-secondary'"
                  >
                    {{ rule.isActive ? '有効' : '無効' }}
                  </span>
                </td>
                <td class="small text-muted" style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                  {{ conditionSummary(rule.condition) }}
                </td>
                <td>
                  <button class="btn btn-sm btn-outline-primary me-1" @click="openEditModal(rule)">
                    編集
                  </button>
                  <button
                    class="btn btn-sm"
                    :class="rule.isActive ? 'btn-outline-warning' : 'btn-outline-success'"
                    @click="toggleActive(rule)"
                  >
                    {{ rule.isActive ? '無効化' : '有効化' }}
                  </button>
                </td>
              </tr>
              <tr v-if="filteredRules.length === 0">
                <td colspan="6" class="text-center text-muted py-3">ルールが見つかりません</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- アラート履歴 -->
    <div class="card">
      <div class="card-header fw-bold d-flex justify-content-between align-items-center">
        <span>アラート履歴（RuleEvaluationLog）</span>
        <span class="badge bg-secondary">{{ alertLogs.length }}件</span>
      </div>
      <div class="card-body p-0">
        <div v-if="alertsLoading" class="text-center py-4">
          <div class="spinner-border spinner-border-sm" role="status"></div>
          <span class="ms-2">読み込み中...</span>
        </div>
        <div v-else-if="alertLogs.length === 0" class="text-muted p-3">
          アラート履歴はありません
        </div>
        <div v-else class="table-responsive">
          <table class="table table-hover mb-0">
            <thead class="table-light">
              <tr>
                <th>日時</th>
                <th>ルール名</th>
                <th>結果</th>
                <th>重要度</th>
                <th>メッセージ</th>
                <th>対象契約</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in alertLogs" :key="log.id">
                <td class="text-nowrap small">{{ formatDate(log.evaluatedAt) }}</td>
                <td>{{ log.ruleName }}</td>
                <td>
                  <span
                    class="badge"
                    :class="resultClass(log.result)"
                  >
                    {{ log.result }}
                  </span>
                </td>
                <td>
                  <span class="badge" :class="severityClass(log.severity)">
                    {{ severityLabel(log.severity) }}
                  </span>
                </td>
                <td class="small">{{ log.message }}</td>
                <td class="small text-muted">{{ log.contractName || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ルール追加/編集モーダル -->
    <div
      class="modal fade"
      id="ruleModal"
      tabindex="-1"
      aria-labelledby="ruleModalLabel"
      aria-hidden="true"
      ref="ruleModal"
    >
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="ruleModalLabel">
              {{ editingRule ? 'ルール編集' : 'ルール追加' }}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="閉じる"></button>
          </div>
          <div class="modal-body">
            <form @submit.prevent="saveRule">
              <!-- ルール名 -->
              <div class="mb-3">
                <label class="form-label fw-bold">ルール名</label>
                <input
                  v-model="ruleForm.name"
                  type="text"
                  class="form-control"
                  placeholder="ルール名を入力"
                  required
                />
              </div>

              <!-- ルール種別 -->
              <div class="mb-3">
                <label class="form-label fw-bold">ルール種別</label>
                <select v-model="ruleForm.ruleType" class="form-select" required>
                  <option value="">-- 選択してください --</option>
                  <option v-for="rt in ruleTypeOptions" :key="rt.value" :value="rt.value">
                    {{ rt.label }}
                  </option>
                </select>
              </div>

              <!-- 重要度 -->
              <div class="mb-3">
                <label class="form-label fw-bold">重要度</label>
                <div>
                  <div class="form-check form-check-inline">
                    <input
                      class="form-check-input"
                      type="radio"
                      v-model="ruleForm.severity"
                      value="INFO"
                      id="severityInfo"
                    />
                    <label class="form-check-label" for="severityInfo">
                      <span class="badge bg-info">情報</span>
                    </label>
                  </div>
                  <div class="form-check form-check-inline">
                    <input
                      class="form-check-input"
                      type="radio"
                      v-model="ruleForm.severity"
                      value="WARNING"
                      id="severityWarning"
                    />
                    <label class="form-check-label" for="severityWarning">
                      <span class="badge bg-warning text-dark">警告</span>
                    </label>
                  </div>
                  <div class="form-check form-check-inline">
                    <input
                      class="form-check-input"
                      type="radio"
                      v-model="ruleForm.severity"
                      value="CRITICAL"
                      id="severityCritical"
                    />
                    <label class="form-check-label" for="severityCritical">
                      <span class="badge bg-danger">緊急</span>
                    </label>
                  </div>
                </div>
              </div>

              <!-- 条件設定（ルール種別に応じたフォーム） -->
              <div class="mb-3">
                <label class="form-label fw-bold">条件設定</label>

                <!-- EXPIRY_ALERT: 日数指定 -->
                <div v-if="ruleForm.ruleType === 'EXPIRY_ALERT'" class="card card-body bg-light">
                  <div class="row align-items-center">
                    <div class="col-auto">
                      <label class="form-label mb-0">契約満了日の</label>
                    </div>
                    <div class="col-auto">
                      <input
                        v-model.number="ruleForm.conditionForm.daysBefore"
                        type="number"
                        class="form-control form-control-sm"
                        style="width: 80px"
                        min="1"
                      />
                    </div>
                    <div class="col-auto">
                      <label class="form-label mb-0">日前に通知</label>
                    </div>
                  </div>
                </div>

                <!-- MISSING_CLAUSE: カテゴリ指定 -->
                <div v-else-if="ruleForm.ruleType === 'MISSING_CLAUSE'" class="card card-body bg-light">
                  <label class="form-label mb-1">必須条項カテゴリ</label>
                  <input
                    v-model="ruleForm.conditionForm.requiredCategory"
                    type="text"
                    class="form-control form-control-sm"
                    placeholder="例: 秘密保持、損害賠償"
                  />
                </div>

                <!-- SCORE_THRESHOLD: スコア閾値 -->
                <div v-else-if="ruleForm.ruleType === 'SCORE_THRESHOLD'" class="card card-body bg-light">
                  <div class="row align-items-center">
                    <div class="col-auto">
                      <label class="form-label mb-0">スコアが</label>
                    </div>
                    <div class="col-auto">
                      <input
                        v-model.number="ruleForm.conditionForm.threshold"
                        type="number"
                        class="form-control form-control-sm"
                        style="width: 80px"
                        min="0"
                        max="100"
                      />
                    </div>
                    <div class="col-auto">
                      <label class="form-label mb-0">未満の場合に通知</label>
                    </div>
                  </div>
                </div>

                <!-- REGULATION_CHANGE: 法令変更 -->
                <div v-else-if="ruleForm.ruleType === 'REGULATION_CHANGE'" class="card card-body bg-light">
                  <label class="form-label mb-1">監視対象の法令キーワード</label>
                  <input
                    v-model="ruleForm.conditionForm.regulationKeyword"
                    type="text"
                    class="form-control form-control-sm"
                    placeholder="例: 下請法、個人情報保護法"
                  />
                </div>

                <!-- CUSTOM: JSON直接入力 -->
                <div v-else-if="ruleForm.ruleType === 'CUSTOM'" class="card card-body bg-light">
                  <label class="form-label mb-1">条件JSON</label>
                  <textarea
                    v-model="ruleForm.conditionForm.rawJson"
                    class="form-control form-control-sm font-monospace"
                    rows="4"
                    placeholder='{ "key": "value" }'
                  ></textarea>
                </div>

                <!-- 種別未選択 -->
                <div v-else class="text-muted small">
                  ルール種別を選択すると条件設定フォームが表示されます
                </div>
              </div>

              <!-- 有効/無効 -->
              <div class="mb-3">
                <div class="form-check form-switch">
                  <input
                    class="form-check-input"
                    type="checkbox"
                    v-model="ruleForm.isActive"
                    id="ruleActiveSwitch"
                  />
                  <label class="form-check-label" for="ruleActiveSwitch">
                    {{ ruleForm.isActive ? '有効' : '無効' }}
                  </label>
                </div>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              キャンセル
            </button>
            <button
              type="button"
              class="btn btn-primary"
              @click="saveRule"
              :disabled="savingRule"
            >
              <span v-if="savingRule">
                <span class="spinner-border spinner-border-sm" role="status"></span>
                保存中...
              </span>
              <span v-else>保存</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'RuleManager',

  data() {
    return {
      // ルール一覧
      rules: [],
      rulesLoading: false,

      // フィルタ
      filterRuleType: '',
      filterSeverity: '',
      filterActive: '',

      // アラート履歴
      alertLogs: [],
      alertsLoading: false,

      // モーダル
      editingRule: null,
      savingRule: false,
      ruleForm: this.defaultRuleForm(),

      // ルール種別選択肢
      ruleTypeOptions: [
        { value: 'EXPIRY_ALERT', label: '契約期限アラート' },
        { value: 'MISSING_CLAUSE', label: '必須条項チェック' },
        { value: 'SCORE_THRESHOLD', label: 'スコア閾値' },
        { value: 'REGULATION_CHANGE', label: '法令変更監視' },
        { value: 'CUSTOM', label: 'カスタム' },
      ],
    };
  },

  computed: {
    filteredRules() {
      return this.rules.filter((r) => {
        if (this.filterRuleType && r.ruleType !== this.filterRuleType) return false;
        if (this.filterSeverity && r.severity !== this.filterSeverity) return false;
        if (this.filterActive !== '') {
          const isActive = this.filterActive === 'true';
          if (r.isActive !== isActive) return false;
        }
        return true;
      });
    },
  },

  created() {
    this.fetchRules();
    this.fetchAlertLogs();
  },

  methods: {
    defaultRuleForm() {
      return {
        name: '',
        ruleType: '',
        severity: 'WARNING',
        isActive: true,
        conditionForm: {
          daysBefore: 30,
          requiredCategory: '',
          threshold: 60,
          regulationKeyword: '',
          rawJson: '',
        },
      };
    },

    async fetchRules() {
      this.rulesLoading = true;
      try {
        const res = await axios.get('/api/v1/tenant/rules/');
        this.rules = res.data.results || res.data || [];
      } catch (err) {
        console.error('ルール一覧の取得に失敗:', err);
      } finally {
        this.rulesLoading = false;
      }
    },

    async fetchAlertLogs() {
      this.alertsLoading = true;
      try {
        const res = await axios.get('/api/v1/tenant/rules/alerts/');
        this.alertLogs = res.data.results || res.data || [];
      } catch (err) {
        console.error('アラート履歴の取得に失敗:', err);
      } finally {
        this.alertsLoading = false;
      }
    },

    openAddModal() {
      this.editingRule = null;
      this.ruleForm = this.defaultRuleForm();
      this.showModal();
    },

    openEditModal(rule) {
      this.editingRule = rule;
      this.ruleForm = {
        name: rule.name || rule.ruleName || '',
        ruleType: rule.ruleType || '',
        severity: rule.severity || 'WARNING',
        isActive: rule.isActive !== false,
        conditionForm: this.parseCondition(rule.ruleType, rule.condition),
      };
      this.showModal();
    },

    showModal() {
      const modalEl = this.$refs.ruleModal;
      if (modalEl && window.bootstrap) {
        const modal = new window.bootstrap.Modal(modalEl);
        modal.show();
      }
    },

    hideModal() {
      const modalEl = this.$refs.ruleModal;
      if (modalEl && window.bootstrap) {
        const modal = window.bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
    },

    parseCondition(ruleType, condition) {
      const form = {
        daysBefore: 30,
        requiredCategory: '',
        threshold: 60,
        regulationKeyword: '',
        rawJson: '',
      };
      if (!condition) return form;
      try {
        const cond = typeof condition === 'string' ? JSON.parse(condition) : condition;
        if (ruleType === 'EXPIRY_ALERT') {
          form.daysBefore = cond.days_before || cond.daysBefore || 30;
        } else if (ruleType === 'MISSING_CLAUSE') {
          form.requiredCategory = cond.required_category || cond.requiredCategory || '';
        } else if (ruleType === 'SCORE_THRESHOLD') {
          form.threshold = cond.threshold || 60;
        } else if (ruleType === 'REGULATION_CHANGE') {
          form.regulationKeyword = cond.regulation_keyword || cond.regulationKeyword || '';
        } else {
          form.rawJson = JSON.stringify(cond, null, 2);
        }
      } catch {
        form.rawJson = String(condition);
      }
      return form;
    },

    buildCondition() {
      const rt = this.ruleForm.ruleType;
      const cf = this.ruleForm.conditionForm;
      if (rt === 'EXPIRY_ALERT') {
        return { days_before: cf.daysBefore };
      } else if (rt === 'MISSING_CLAUSE') {
        return { required_category: cf.requiredCategory };
      } else if (rt === 'SCORE_THRESHOLD') {
        return { threshold: cf.threshold };
      } else if (rt === 'REGULATION_CHANGE') {
        return { regulation_keyword: cf.regulationKeyword };
      } else if (rt === 'CUSTOM') {
        try {
          return JSON.parse(cf.rawJson);
        } catch {
          return { raw: cf.rawJson };
        }
      }
      return {};
    },

    async saveRule() {
      this.savingRule = true;
      const payload = {
        name: this.ruleForm.name,
        rule_type: this.ruleForm.ruleType,
        severity: this.ruleForm.severity,
        is_active: this.ruleForm.isActive,
        condition: this.buildCondition(),
      };
      try {
        if (this.editingRule) {
          await axios.put(`/api/v1/tenant/rules/${this.editingRule.id}/`, payload);
        } else {
          await axios.post('/api/v1/tenant/rules/', payload);
        }
        this.hideModal();
        this.fetchRules();
      } catch (err) {
        console.error('ルールの保存に失敗:', err);
        alert('ルールの保存に失敗しました。入力内容を確認してください。');
      } finally {
        this.savingRule = false;
      }
    },

    async toggleActive(rule) {
      try {
        await axios.put(`/api/v1/tenant/rules/${rule.id}/`, {
          is_active: !rule.isActive,
        });
        rule.isActive = !rule.isActive;
      } catch (err) {
        console.error('ルール状態の更新に失敗:', err);
      }
    },

    conditionSummary(condition) {
      if (!condition) return '-';
      try {
        const cond = typeof condition === 'string' ? JSON.parse(condition) : condition;
        if (cond.days_before || cond.daysBefore) {
          return `${cond.days_before || cond.daysBefore}日前に通知`;
        }
        if (cond.required_category || cond.requiredCategory) {
          return `必須: ${cond.required_category || cond.requiredCategory}`;
        }
        if (cond.threshold) {
          return `スコア < ${cond.threshold}`;
        }
        if (cond.regulation_keyword || cond.regulationKeyword) {
          return `法令: ${cond.regulation_keyword || cond.regulationKeyword}`;
        }
        return JSON.stringify(cond);
      } catch {
        return String(condition);
      }
    },

    formatDate(dateStr) {
      if (!dateStr) return '-';
      const d = new Date(dateStr);
      return d.toLocaleDateString('ja-JP') + ' ' + d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
    },

    ruleTypeLabel(ruleType) {
      const option = this.ruleTypeOptions.find((o) => o.value === ruleType);
      return option ? option.label : ruleType;
    },

    severityClass(severity) {
      const map = { CRITICAL: 'bg-danger', WARNING: 'bg-warning text-dark', INFO: 'bg-info' };
      return map[severity] || 'bg-secondary';
    },

    severityLabel(severity) {
      const map = { CRITICAL: '緊急', WARNING: '警告', INFO: '情報' };
      return map[severity] || severity;
    },

    resultClass(result) {
      const map = { PASS: 'bg-success', WARN: 'bg-warning text-dark', FAIL: 'bg-danger' };
      return map[result] || 'bg-secondary';
    },
  },
};
</script>

<style scoped>
.font-monospace {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}
</style>
