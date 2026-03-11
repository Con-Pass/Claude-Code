<template>
  <div class="container py-4">
    <!-- ヘッダー -->
    <div class="text-center mb-5">
      <h1 class="display-5 fw-bold">契約は、力だ。</h1>
      <p class="lead text-muted">あなたのビジネスに最適なプランを選び、契約管理の力を手に入れましょう。</p>
    </div>

    <!-- プラン比較テーブル -->
    <div class="row g-4 mb-5">
      <!-- Lightプラン -->
      <div class="col-md-4">
        <div class="card h-100 border-secondary">
          <div class="card-header bg-secondary text-white text-center py-3">
            <h4 class="mb-0">Light</h4>
            <small>まずは試してみたい方に</small>
          </div>
          <div class="card-body">
            <div class="text-center mb-3">
              <span class="display-6 fw-bold">無料</span>
            </div>
            <ul class="list-unstyled">
              <li v-for="feature in features" :key="feature.name" class="py-2 border-bottom d-flex align-items-center">
                <span v-if="feature.light" class="text-success me-2">&#x2713;</span>
                <span v-else class="text-muted me-2">&#x2014;</span>
                <span :class="{ 'text-muted': !feature.light }">{{ feature.name }}</span>
              </li>
            </ul>
          </div>
          <div class="card-footer text-center bg-white border-0 pb-3">
            <button class="btn btn-outline-secondary w-100" disabled>現在のプラン</button>
          </div>
        </div>
      </div>

      <!-- Standardプラン（推奨） -->
      <div class="col-md-4">
        <div class="card h-100 border-warning shadow-lg">
          <div class="card-header bg-warning text-dark text-center py-3 position-relative">
            <span class="badge bg-danger position-absolute top-0 start-50 translate-middle">おすすめ</span>
            <h4 class="mb-0 mt-2">Standard</h4>
            <small>本格的な契約管理に</small>
          </div>
          <div class="card-body">
            <div class="text-center mb-3">
              <span class="display-6 fw-bold">&#xA5;9,800</span>
              <span class="text-muted">/月</span>
            </div>
            <ul class="list-unstyled">
              <li v-for="feature in features" :key="feature.name" class="py-2 border-bottom d-flex align-items-center">
                <span v-if="feature.standard" class="text-success me-2">&#x2713;</span>
                <span v-else class="text-muted me-2">&#x2014;</span>
                <span :class="{ 'text-muted': !feature.standard }">{{ feature.name }}</span>
                <span v-if="feature.standardNote" class="badge bg-info ms-auto">{{ feature.standardNote }}</span>
              </li>
            </ul>
          </div>
          <div class="card-footer text-center bg-white border-0 pb-3">
            <button @click="selectPlan('standard')" class="btn btn-warning btn-lg w-100 fw-bold">
              STプランへアップグレード
            </button>
          </div>
        </div>
      </div>

      <!-- Standard Plusプラン -->
      <div class="col-md-4">
        <div class="card h-100 border-primary">
          <div class="card-header bg-primary text-white text-center py-3">
            <h4 class="mb-0">Standard Plus</h4>
            <small>士業・大企業向け</small>
          </div>
          <div class="card-body">
            <div class="text-center mb-3">
              <span class="display-6 fw-bold">&#xA5;29,800</span>
              <span class="text-muted">/月</span>
            </div>
            <ul class="list-unstyled">
              <li v-for="feature in features" :key="feature.name" class="py-2 border-bottom d-flex align-items-center">
                <span v-if="feature.plus" class="text-success me-2">&#x2713;</span>
                <span v-else class="text-muted me-2">&#x2014;</span>
                <span :class="{ 'text-muted': !feature.plus }">{{ feature.name }}</span>
                <span v-if="feature.plusNote" class="badge bg-info ms-auto">{{ feature.plusNote }}</span>
              </li>
            </ul>
          </div>
          <div class="card-footer text-center bg-white border-0 pb-3">
            <button @click="selectPlan('standard_plus')" class="btn btn-primary btn-lg w-100 fw-bold">
              ST Plusへアップグレード
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 機能詳細ベネフィット -->
    <div class="card mb-4">
      <div class="card-header bg-light">
        <h5 class="mb-0">STプランで解放される機能</h5>
      </div>
      <div class="card-body">
        <div class="row g-3">
          <div v-for="benefit in benefits" :key="benefit.command" class="col-md-6">
            <div class="d-flex align-items-start p-3 border rounded">
              <code class="me-3 text-nowrap">{{ benefit.command }}</code>
              <div>
                <strong>{{ benefit.title }}</strong>
                <br>
                <small class="text-muted">{{ benefit.description }}</small>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- アップグレード確認モーダル -->
    <div v-if="showConfirmModal" class="modal d-block" tabindex="-1" style="background: rgba(0,0,0,0.5);">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">プランアップグレードの確認</h5>
            <button type="button" class="btn-close" @click="showConfirmModal = false"></button>
          </div>
          <div class="modal-body">
            <p><strong>{{ selectedPlanName }}</strong>へのアップグレードを開始します。</p>
            <p class="text-muted">アップグレード後、オンボーディングウィザードで初期設定を行います。</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="showConfirmModal = false">キャンセル</button>
            <button type="button" class="btn btn-warning fw-bold" @click="confirmUpgrade">アップグレードを確定</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../services/api'

export default {
  name: 'PlanCompare',
  data() {
    return {
      showConfirmModal: false,
      selectedPlan: null,
      features: [
        { name: '契約書アップロード・保管', light: true, standard: true, plus: true },
        { name: '基本メタデータ管理', light: true, standard: true, plus: true },
        { name: '期限アラート（30日前）', light: true, standard: true, plus: true },
        { name: '/review-contract（12条項自動分析）', light: false, standard: true, plus: true, standardNote: '交渉を有利に' },
        { name: '/brief daily（毎朝サマリー配信）', light: false, standard: true, plus: true },
        { name: '/respond（AI交渉文案生成）', light: false, standard: true, plus: true },
        { name: '/vendor-check（取引先リスク調査）', light: false, standard: true, plus: true },
        { name: 'Playbookエンジン', light: false, standard: true, plus: true, standardNote: '自社ルール反映' },
        { name: 'コンプライアンススコア', light: false, standard: true, plus: true },
        { name: 'テンプレート比較', light: false, standard: true, plus: true },
        { name: '法令改正アラート', light: false, standard: false, plus: true, plusNote: 'e-Gov連携' },
        { name: '業界団体OEMダッシュボード', light: false, standard: false, plus: true },
        { name: 'マルチテナント顧問先管理', light: false, standard: false, plus: true, plusNote: '士業向け' },
        { name: 'API連携（GMO Sign等）', light: false, standard: false, plus: true }
      ],
      benefits: [
        {
          command: '/review-contract',
          title: '12条項を自動分析、交渉を有利に',
          description: '契約書をアップロードするだけで、12の重要条項を自動で分析。リスクポイントを見逃しません。'
        },
        {
          command: '/brief daily',
          title: '毎朝、契約の状況を1分で把握',
          description: '期限切れ間近の契約、注意すべきリスク、最新の法改正影響をサマリーでお届けします。'
        },
        {
          command: '/respond',
          title: 'AI交渉文案で、プロの対応力を',
          description: '取引先からの契約修正要求に対し、自社ポリシーに基づいた交渉文案をAIが生成します。'
        },
        {
          command: '/vendor-check',
          title: '取引先リスクを事前に把握',
          description: '新規取引先の信用情報・訴訟履歴・反社チェックをワンクリックで実行できます。'
        }
      ]
    }
  },
  computed: {
    selectedPlanName() {
      if (this.selectedPlan === 'standard') return 'Standardプラン'
      if (this.selectedPlan === 'standard_plus') return 'Standard Plusプラン'
      return ''
    }
  },
  methods: {
    selectPlan(plan) {
      this.selectedPlan = plan
      this.showConfirmModal = true
    },
    async confirmUpgrade() {
      try {
        await api.post('/tenant/upgrade/', { plan: this.selectedPlan })
        this.showConfirmModal = false
        this.$router.push('/onboarding')
      } catch (error) {
        alert('アップグレード処理中にエラーが発生しました。サポートにお問い合わせください。')
      }
    }
  }
}
</script>

<style scoped>
.card.border-warning {
  border-width: 2px;
}
</style>
