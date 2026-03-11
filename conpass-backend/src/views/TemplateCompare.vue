<template>
  <div class="container py-4">
    <h2 class="fw-bold mb-1">テンプレート比較</h2>
    <p class="text-muted mb-4">契約書をテンプレートと比較し、条項ごとのギャップを確認します。</p>

    <!-- 比較設定パネル -->
    <div class="card mb-4">
      <div class="card-body">
        <div class="row g-3 align-items-end">
          <div class="col-md-4">
            <label class="form-label fw-bold">契約書を選択</label>
            <select v-model="selectedContract" class="form-select">
              <option :value="null" disabled>-- 契約書を選択 --</option>
              <option v-for="c in contracts" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </div>
          <div class="col-md-4">
            <label class="form-label fw-bold">テンプレートを選択</label>
            <select v-model="selectedTemplate" class="form-select" :disabled="loadingTemplates">
              <option :value="null" disabled>-- テンプレートを選択 --</option>
              <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </div>
          <div class="col-md-4">
            <button
              class="btn btn-primary w-100"
              :disabled="!selectedContract || !selectedTemplate || comparing"
              @click="runCompare"
            >
              <span v-if="comparing" class="spinner-border spinner-border-sm me-1"></span>
              比較実行
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 比較結果 -->
    <div v-if="result" class="card">
      <div class="card-header bg-light d-flex justify-content-between align-items-center">
        <h5 class="mb-0">比較結果</h5>
        <div>
          <span class="badge bg-success me-1">GREEN {{ greenCount }}件</span>
          <span class="badge bg-warning text-dark me-1">YELLOW {{ yellowCount }}件</span>
          <span class="badge bg-danger">RED {{ redCount }}件</span>
        </div>
      </div>
      <div class="card-body p-0">
        <div class="accordion" id="compareAccordion">
          <div
            v-for="(clause, idx) in result.clauses"
            :key="idx"
            class="accordion-item"
          >
            <h2 class="accordion-header">
              <button
                class="accordion-button collapsed"
                type="button"
                :data-bs-toggle="'collapse'"
                :data-bs-target="'#clause-' + idx"
              >
                <span
                  class="badge me-2"
                  :class="statusBadgeClass(clause.status)"
                >{{ clause.status }}</span>
                {{ clause.clause_name }}
              </button>
            </h2>
            <div :id="'clause-' + idx" class="accordion-collapse collapse">
              <div class="accordion-body">
                <!-- 差分表示 -->
                <div class="row g-3 mb-3">
                  <div class="col-md-6">
                    <h6 class="text-muted">契約書の条項</h6>
                    <div class="border rounded p-3 bg-light">
                      <pre class="mb-0" style="white-space: pre-wrap; font-size: 0.9rem;">{{ clause.contract_text || '（該当条項なし）' }}</pre>
                    </div>
                  </div>
                  <div class="col-md-6">
                    <h6 class="text-muted">テンプレートの条項</h6>
                    <div class="border rounded p-3 bg-light">
                      <pre class="mb-0" style="white-space: pre-wrap; font-size: 0.9rem;">{{ clause.template_text || '（該当条項なし）' }}</pre>
                    </div>
                  </div>
                </div>

                <!-- 差分ハイライト -->
                <div v-if="clause.differences && clause.differences.length" class="mb-3">
                  <h6>差分箇所</h6>
                  <div
                    v-for="(diff, didx) in clause.differences"
                    :key="didx"
                    class="p-2 mb-2 rounded"
                    :class="diffClass(diff.type)"
                  >
                    <small class="fw-bold">{{ diffLabel(diff.type) }}</small>
                    <span class="ms-2">{{ diff.text }}</span>
                  </div>
                </div>

                <!-- 修正提案 -->
                <div v-if="clause.suggestion" class="mb-3">
                  <h6>修正提案</h6>
                  <div class="border rounded p-3 bg-white">
                    <pre class="mb-0" style="white-space: pre-wrap; font-size: 0.9rem;">{{ clause.suggestion }}</pre>
                  </div>
                  <button
                    class="btn btn-outline-primary btn-sm mt-2"
                    @click="copySuggestion(clause.suggestion)"
                  >
                    修正提案をコピー
                  </button>
                  <span v-if="copiedIdx === idx" class="text-success ms-2 small">コピーしました</span>
                </div>

                <!-- 分析コメント -->
                <div v-if="clause.analysis" class="alert alert-info mb-0">
                  <small>{{ clause.analysis }}</small>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 結果なし -->
    <div v-if="noResult" class="text-center py-5 text-muted">
      <p>契約書とテンプレートを選択し、「比較実行」をクリックしてください。</p>
    </div>
  </div>
</template>

<script>
import api from '../services/api'

export default {
  name: 'TemplateCompare',
  data() {
    return {
      contracts: [],
      templates: [],
      selectedContract: null,
      selectedTemplate: null,
      loadingTemplates: false,
      comparing: false,
      result: null,
      copiedIdx: null
    }
  },
  computed: {
    noResult() {
      return !this.result && !this.comparing
    },
    greenCount() {
      if (!this.result) return 0
      return this.result.clauses.filter(c => c.status === 'GREEN').length
    },
    yellowCount() {
      if (!this.result) return 0
      return this.result.clauses.filter(c => c.status === 'YELLOW').length
    },
    redCount() {
      if (!this.result) return 0
      return this.result.clauses.filter(c => c.status === 'RED').length
    }
  },
  created() {
    this.fetchContracts()
    this.fetchTemplates()
  },
  methods: {
    statusBadgeClass(status) {
      const map = {
        GREEN: 'bg-success',
        YELLOW: 'bg-warning text-dark',
        RED: 'bg-danger'
      }
      return map[status] || 'bg-secondary'
    },
    diffClass(type) {
      if (type === 'added') return 'bg-success bg-opacity-10 border-start border-3 border-success'
      if (type === 'removed') return 'bg-danger bg-opacity-10 border-start border-3 border-danger'
      return 'bg-warning bg-opacity-10 border-start border-3 border-warning'
    },
    diffLabel(type) {
      if (type === 'added') return '[追加]'
      if (type === 'removed') return '[削除]'
      return '[変更]'
    },
    async fetchContracts() {
      try {
        const res = await api.get('/contracts/')
        this.contracts = res.data.results || res.data
      } catch {
        this.contracts = [
          { id: 1, name: '業務委託基本契約書 - 株式会社サンプル' },
          { id: 2, name: 'ソフトウェアライセンス契約 - テック株式会社' },
          { id: 3, name: '秘密保持契約書 - 株式会社パートナー' }
        ]
      }
    },
    async fetchTemplates() {
      this.loadingTemplates = true
      try {
        const res = await api.get('/template/list')
        this.templates = res.data.results || res.data
      } catch {
        this.templates = [
          { id: 1, name: '業務委託契約テンプレート（IT業界標準）' },
          { id: 2, name: 'SaaSライセンス契約テンプレート' },
          { id: 3, name: '秘密保持契約テンプレート（標準）' },
          { id: 4, name: '取引基本契約テンプレート' }
        ]
      } finally {
        this.loadingTemplates = false
      }
    },
    async runCompare() {
      this.comparing = true
      this.result = null
      try {
        const res = await api.post('/template/compare', {
          contract_id: this.selectedContract,
          template_id: this.selectedTemplate
        })
        this.result = res.data
      } catch {
        // デモ結果
        this.result = {
          clauses: [
            {
              clause_name: '契約期間',
              status: 'GREEN',
              contract_text: '本契約の有効期間は、締結日から1年間とする。ただし、期間満了の3ヶ月前までに書面による解約の申し出がない限り、自動的に1年間更新されるものとする。',
              template_text: '本契約の有効期間は、締結日から1年間とする。期間満了の3ヶ月前までに書面通知がない場合、同条件で1年間自動更新する。',
              differences: [],
              suggestion: null,
              analysis: '契約期間・自動更新条件ともにテンプレートと整合しています。'
            },
            {
              clause_name: '秘密保持',
              status: 'YELLOW',
              contract_text: '甲及び乙は、本契約に関連して知り得た相手方の秘密情報を、本契約の目的以外に使用してはならない。',
              template_text: '甲及び乙は、本契約に関連して知り得た相手方の秘密情報を、本契約の目的以外に使用し、又は第三者に開示・漏洩してはならない。秘密保持義務は、本契約終了後3年間存続するものとする。',
              differences: [
                { type: 'removed', text: '第三者への開示・漏洩禁止が明記されていない' },
                { type: 'removed', text: '秘密保持期間（契約終了後の存続期間）の定めがない' }
              ],
              suggestion: '甲及び乙は、本契約に関連して知り得た相手方の秘密情報を、本契約の目的以外に使用し、又は第三者に開示・漏洩してはならない。本項に定める秘密保持義務は、本契約終了後3年間存続するものとする。',
              analysis: '秘密保持条項に第三者開示禁止と存続期間の記載が不足しています。追記を推奨します。'
            },
            {
              clause_name: '損害賠償',
              status: 'RED',
              contract_text: null,
              template_text: '甲又は乙が本契約に違反し、相手方に損害を与えた場合、直接かつ通常の損害に限り、賠償する責任を負う。ただし、賠償額の上限は、本契約に基づき過去12ヶ月間に支払われた対価の総額とする。',
              differences: [
                { type: 'removed', text: '損害賠償条項が契約書に存在しない' }
              ],
              suggestion: '第X条（損害賠償）\n甲又は乙が本契約に違反し、相手方に損害を与えた場合、直接かつ通常の損害に限り、賠償する責任を負う。ただし、賠償額の上限は、本契約に基づき過去12ヶ月間に支払われた対価の総額とする。',
              analysis: '損害賠償条項が欠落しています。契約リスクが高い状態です。早急な追加を強く推奨します。'
            },
            {
              clause_name: '解除',
              status: 'GREEN',
              contract_text: '甲又は乙は、相手方が本契約に違反し、催告後30日以内に是正されない場合、本契約を解除することができる。',
              template_text: '甲又は乙は、相手方が本契約に違反し、書面による催告後30日以内に当該違反が是正されない場合、本契約を解除することができる。',
              differences: [],
              suggestion: null,
              analysis: '解除条件はテンプレートとほぼ一致しています。'
            },
            {
              clause_name: '知的財産権',
              status: 'YELLOW',
              contract_text: '本契約に基づき作成された成果物の知的財産権は、対価の支払完了時に乙から甲に移転する。',
              template_text: '本契約に基づき作成された成果物の著作権（著作権法第27条及び第28条の権利を含む）は、対価の支払完了時に乙から甲に移転する。なお、乙は甲に対し著作者人格権を行使しないものとする。',
              differences: [
                { type: 'changed', text: '著作権法27条・28条の権利が明示されていない' },
                { type: 'removed', text: '著作者人格権不行使の定めがない' }
              ],
              suggestion: '本契約に基づき作成された成果物の著作権（著作権法第27条及び第28条の権利を含む）その他一切の知的財産権は、対価の支払完了時に乙から甲に移転する。なお、乙は甲に対し著作者人格権を行使しないものとする。',
              analysis: '著作権移転に関して著作権法27条・28条の明示と著作者人格権不行使の定めが不足しています。'
            }
          ]
        }
      } finally {
        this.comparing = false
      }
    },
    async copySuggestion(text) {
      try {
        await navigator.clipboard.writeText(text)
        this.copiedIdx = true
        setTimeout(() => { this.copiedIdx = null }, 2000)
      } catch {
        // フォールバック
        const textarea = document.createElement('textarea')
        textarea.value = text
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
        this.copiedIdx = true
        setTimeout(() => { this.copiedIdx = null }, 2000)
      }
    }
  }
}
</script>
