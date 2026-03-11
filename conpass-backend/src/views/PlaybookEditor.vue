<template>
  <div class="container-fluid py-4">
    <h2 class="mb-4">Playbook エディタ</h2>

    <!-- テンプレート選択 -->
    <div class="card mb-4">
      <div class="card-header fw-bold">テンプレート選択</div>
      <div class="card-body">
        <div class="row align-items-end">
          <div class="col-md-4">
            <label class="form-label">業種別テンプレート</label>
            <select v-model="selectedTemplateId" class="form-select">
              <option value="">-- テンプレートを選択 --</option>
              <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">
                {{ tpl.name }} ({{ tpl.industry }})
              </option>
            </select>
          </div>
          <div class="col-md-4">
            <label class="form-label">Playbook</label>
            <select v-model="selectedPlaybookId" class="form-select">
              <option value="">-- Playbookを選択 --</option>
              <option v-for="pb in playbooks" :key="pb.id" :value="pb.id">
                {{ pb.name }}
              </option>
            </select>
          </div>
          <div class="col-md-4">
            <button
              class="btn btn-primary"
              @click="applyTemplate"
              :disabled="!selectedTemplateId || !selectedPlaybookId || applyingTemplate"
            >
              <span v-if="applyingTemplate">
                <span class="spinner-border spinner-border-sm" role="status"></span>
                適用中...
              </span>
              <span v-else>テンプレート適用</span>
            </button>
          </div>
        </div>
        <div v-if="templateMessage" class="alert mt-3" :class="templateMessageClass">
          {{ templateMessage }}
        </div>
      </div>
    </div>

    <!-- 12条項カテゴリ アコーディオン -->
    <div class="card">
      <div class="card-header fw-bold d-flex justify-content-between align-items-center">
        <span>条項ポリシー設定</span>
        <button class="btn btn-sm btn-success" @click="saveAllClauses" :disabled="saving">
          <span v-if="saving">
            <span class="spinner-border spinner-border-sm" role="status"></span>
            保存中...
          </span>
          <span v-else>全て保存</span>
        </button>
      </div>
      <div class="card-body">
        <div v-if="clausesLoading" class="text-center py-4">
          <div class="spinner-border" role="status"></div>
          <p class="mt-2">条項を読み込み中...</p>
        </div>

        <div v-else-if="clauses.length === 0" class="text-muted">
          Playbookを選択してください
        </div>

        <div v-else class="accordion" id="clauseAccordion">
          <div v-for="(clause, index) in clauses" :key="clause.id" class="accordion-item">
            <h2 class="accordion-header" :id="'heading-' + index">
              <button
                class="accordion-button"
                :class="{ collapsed: index !== 0 }"
                type="button"
                data-bs-toggle="collapse"
                :data-bs-target="'#collapse-' + index"
                :aria-expanded="index === 0 ? 'true' : 'false'"
                :aria-controls="'collapse-' + index"
              >
                <span class="me-2 badge bg-secondary">{{ index + 1 }}</span>
                {{ clause.category }}
                <span
                  v-if="clause.modified"
                  class="ms-2 badge bg-info"
                >編集済</span>
              </button>
            </h2>
            <div
              :id="'collapse-' + index"
              class="accordion-collapse collapse"
              :class="{ show: index === 0 }"
              :aria-labelledby="'heading-' + index"
              data-bs-parent="#clauseAccordion"
            >
              <div class="accordion-body">
                <!-- GREEN基準 -->
                <div class="mb-3">
                  <label class="form-label fw-bold">
                    <span class="badge bg-success me-1">GREEN</span>
                    承認基準
                  </label>
                  <textarea
                    v-model="clause.greenCriteria"
                    class="form-control clause-textarea green-textarea"
                    rows="3"
                    placeholder="GREEN基準を入力（そのまま承認できる条件）..."
                    @input="clause.modified = true"
                  ></textarea>
                </div>

                <!-- YELLOW境界条件 -->
                <div class="mb-3">
                  <label class="form-label fw-bold">
                    <span class="badge bg-warning text-dark me-1">YELLOW</span>
                    境界条件
                  </label>
                  <textarea
                    v-model="clause.yellowCriteria"
                    class="form-control clause-textarea yellow-textarea"
                    rows="3"
                    placeholder="YELLOW基準を入力（条件付きで承認できる境界条件）..."
                    @input="clause.modified = true"
                  ></textarea>
                </div>

                <!-- RED エスカレーション -->
                <div class="mb-3">
                  <label class="form-label fw-bold">
                    <span class="badge bg-danger me-1">RED</span>
                    エスカレーショントリガー
                  </label>
                  <textarea
                    v-model="clause.redCriteria"
                    class="form-control clause-textarea red-textarea"
                    rows="3"
                    placeholder="RED基準を入力（エスカレーションが必要な条件）..."
                    @input="clause.modified = true"
                  ></textarea>
                </div>

                <!-- 個別保存 -->
                <div class="text-end">
                  <button
                    class="btn btn-sm btn-outline-primary"
                    @click="saveClause(clause)"
                    :disabled="!clause.modified || saving"
                  >
                    この条項を保存
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="saveMessage" class="alert mt-3" :class="saveMessageClass">
          {{ saveMessage }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'PlaybookEditor',

  data() {
    return {
      // テンプレート
      templates: [],
      selectedTemplateId: '',
      applyingTemplate: false,
      templateMessage: '',
      templateMessageClass: '',

      // Playbook
      playbooks: [],
      selectedPlaybookId: '',

      // 条項
      clauses: [],
      clausesLoading: false,

      // 保存
      saving: false,
      saveMessage: '',
      saveMessageClass: '',
    };
  },

  watch: {
    selectedPlaybookId(newVal) {
      if (newVal) {
        this.fetchClauses(newVal);
      } else {
        this.clauses = [];
      }
    },
  },

  created() {
    this.fetchTemplates();
    this.fetchPlaybooks();
  },

  methods: {
    async fetchTemplates() {
      try {
        const res = await axios.get('/api/v1/tenant/playbook/templates/');
        this.templates = res.data.results || res.data || [];
      } catch (err) {
        console.error('テンプレート一覧の取得に失敗:', err);
      }
    },

    async fetchPlaybooks() {
      try {
        const res = await axios.get('/api/v1/tenant/playbook/');
        this.playbooks = res.data.results || res.data || [];
        if (this.playbooks.length > 0 && !this.selectedPlaybookId) {
          this.selectedPlaybookId = this.playbooks[0].id;
        }
      } catch (err) {
        console.error('Playbook一覧の取得に失敗:', err);
      }
    },

    async fetchClauses(playbookId) {
      this.clausesLoading = true;
      this.clauses = [];
      try {
        const res = await axios.get(`/api/v1/tenant/playbook/${playbookId}/clauses/`);
        this.clauses = (res.data.results || res.data || []).map((c) => ({
          ...c,
          greenCriteria: c.greenCriteria || c.green_criteria || '',
          yellowCriteria: c.yellowCriteria || c.yellow_criteria || '',
          redCriteria: c.redCriteria || c.red_criteria || '',
          modified: false,
        }));
      } catch (err) {
        console.error('条項の取得に失敗:', err);
      } finally {
        this.clausesLoading = false;
      }
    },

    async applyTemplate() {
      if (!this.selectedTemplateId || !this.selectedPlaybookId) return;
      this.applyingTemplate = true;
      this.templateMessage = '';
      try {
        await axios.post(
          `/api/v1/tenant/playbook/${this.selectedPlaybookId}/apply-template/`,
          { template_id: this.selectedTemplateId }
        );
        this.templateMessage = 'テンプレートを適用しました';
        this.templateMessageClass = 'alert-success';
        this.fetchClauses(this.selectedPlaybookId);
      } catch (err) {
        console.error('テンプレート適用に失敗:', err);
        this.templateMessage = 'テンプレートの適用に失敗しました';
        this.templateMessageClass = 'alert-danger';
      } finally {
        this.applyingTemplate = false;
      }
    },

    async saveClause(clause) {
      this.saving = true;
      this.saveMessage = '';
      try {
        await axios.put(
          `/api/v1/tenant/playbook/${this.selectedPlaybookId}/clauses/${clause.id}/`,
          {
            green_criteria: clause.greenCriteria,
            yellow_criteria: clause.yellowCriteria,
            red_criteria: clause.redCriteria,
          }
        );
        clause.modified = false;
        this.saveMessage = `「${clause.category}」を保存しました`;
        this.saveMessageClass = 'alert-success';
      } catch (err) {
        console.error('条項の保存に失敗:', err);
        this.saveMessage = `「${clause.category}」の保存に失敗しました`;
        this.saveMessageClass = 'alert-danger';
      } finally {
        this.saving = false;
      }
    },

    async saveAllClauses() {
      const modified = this.clauses.filter((c) => c.modified);
      if (modified.length === 0) {
        this.saveMessage = '変更された条項はありません';
        this.saveMessageClass = 'alert-info';
        return;
      }
      this.saving = true;
      this.saveMessage = '';
      let successCount = 0;
      let failCount = 0;
      for (const clause of modified) {
        try {
          await axios.put(
            `/api/v1/tenant/playbook/${this.selectedPlaybookId}/clauses/${clause.id}/`,
            {
              green_criteria: clause.greenCriteria,
              yellow_criteria: clause.yellowCriteria,
              red_criteria: clause.redCriteria,
            }
          );
          clause.modified = false;
          successCount++;
        } catch (err) {
          console.error(`条項 ${clause.category} の保存に失敗:`, err);
          failCount++;
        }
      }
      this.saving = false;
      if (failCount === 0) {
        this.saveMessage = `${successCount}件の条項を保存しました`;
        this.saveMessageClass = 'alert-success';
      } else {
        this.saveMessage = `${successCount}件成功、${failCount}件失敗`;
        this.saveMessageClass = 'alert-warning';
      }
    },
  },
};
</script>

<style scoped>
.clause-textarea {
  font-size: 0.9rem;
}
.green-textarea {
  background-color: #d1e7dd;
  border-color: #198754;
}
.green-textarea:focus {
  background-color: #c3e0d3;
  border-color: #198754;
  box-shadow: 0 0 0 0.2rem rgba(25, 135, 84, 0.25);
}
.yellow-textarea {
  background-color: #fff3cd;
  border-color: #ffc107;
}
.yellow-textarea:focus {
  background-color: #ffecb5;
  border-color: #ffc107;
  box-shadow: 0 0 0 0.2rem rgba(255, 193, 7, 0.25);
}
.red-textarea {
  background-color: #f8d7da;
  border-color: #dc3545;
}
.red-textarea:focus {
  background-color: #f1c0c5;
  border-color: #dc3545;
  box-shadow: 0 0 0 0.2rem rgba(220, 53, 69, 0.25);
}
</style>
