# ConPass プロトタイプ テストシナリオ

> 作成日: 2026-02-20
> 対象: MS1 プロトタイプ (STプラン)

---

## ペルソナ1: 山田正（建設会社総務部長）
### シナリオ: 取引先チェックと期限管理

**前提条件**: STプランでログイン済み / Account に複数契約が登録済み / PlaybookTemplate「建設業」適用済み

| # | 操作 | 期待結果 | API | 備考 |
|---|------|---------|-----|------|
| 1 | ログイン → ダッシュボード表示 | ConPassスコア（0-100）が表示される。期限アラート・コンプライアンスサマリが表示される | GET /api/v1/compliance/summary | スコアは TenantRule 評価結果の集計 |
| 2 | 期限アラートの「株式会社〇〇 工事請負契約」をクリック | 契約詳細画面が開き、契約名・相手方・期限・ステータスが表示される | GET /api/v1/contracts/{id}/ | MetaData から contractenddate を取得 |
| 3 | vendor-checkパネルで「株式会社〇〇」を入力して実行 | Vendor Check Report が表示される。NDA未締結のギャップが RED で表示される | POST /api/v1/legal/vendor-check | ClausePolicy の escalation_triggers で判定 |
| 4 | AIアシスタントで「この契約の損害賠償条項を確認して」と入力 | 損害賠償条項の分析結果が返る。GREEN/YELLOW/RED 分類と根拠条文が表示される | POST /api/v1/chat | LLM が ClausePolicy(LIABILITY) を参照 |
| 5 | /review-contract で主要契約をレビュー | 全条項の GREEN/YELLOW/RED 分類が一覧表示される。RED 項目にはエスカレーション推奨が付く | POST /api/v1/legal/review-contract | PlaybookEngine の ClausePolicy 全種別を評価 |
| 6 | RED 判定の損害賠償条項をクリック → 詳細確認 | 条項原文・Playbook基準・逸脱内容・推奨アクションが表示される | - | フロントエンド表示のみ |
| 7 | 「期限90日前アラート」が表示されていることを確認 | TenantRule(EXPIRY_ALERT) が WARN を出し、ダッシュボードにアラートカードが表示される | GET /api/v1/compliance/alerts | RuleEvaluationLog に WARN 記録あり |

### 検証ポイント
- TenantRule の EXPIRY_ALERT が正しく 90日前に発火するか
- ClausePolicy の GREEN/YELLOW/RED 分類が Playbook 設定と一致するか
- Vendor Check で NDA 未締結が正しく検出されるか

---

## ペルソナ2: 佐藤恵子（不動産管理会社経営者）
### シナリオ: NDAトリアージとコンプライアンスダッシュボード

**前提条件**: STプランでログイン済み / PlaybookTemplate「不動産」適用済み / 複数NDAが登録済み

| # | 操作 | 期待結果 | API | 備考 |
|---|------|---------|-----|------|
| 1 | ログイン → コンプライアンスダッシュボードを開く | 全体スコア・契約種別ごとのスコア・期限カレンダーが表示される | GET /api/v1/compliance/summary | 不動産業テンプレートの基準で算出 |
| 2 | /triage-nda で受領済みNDAを選択してトリアージ実行 | NDAが GREEN/YELLOW/RED に分類される。相互性・期間・除外規定・守秘義務範囲が評価される | POST /api/v1/legal/triage-nda | ClausePolicy(CONFIDENTIALITY) を主に参照 |
| 3 | RED判定のNDA（一方的NDA）の詳細を確認 | 「相互性なし」「相手方の守秘義務が不十分」などの指摘が表示される | - | triage-nda レスポンスの detail フィールド |
| 4 | YELLOW判定のNDA（微細な逸脱あり）を確認 | 「期間が標準(3年)より長い(5年)」などの指摘と交渉推奨ポイントが表示される | - | acceptable_range との比較結果 |
| 5 | コンプライアンスダッシュボードで「必須契約」セクションを確認 | 管理物件ごとに必須契約（賃貸借契約・管理委託契約・火災保険証書）の充足状況が表示される | GET /api/v1/compliance/required-contracts | TenantRule(REQUIRED_CONTRACT) の評価結果 |
| 6 | 未締結の管理委託契約をクリック | 「管理委託契約が未登録です」の警告と、テンプレートからの作成リンクが表示される | - | FAIL 結果の detail にアクション提案 |
| 7 | スコア推移グラフで先月比を確認 | コンプライアンススコアの月次推移が折れ線グラフで表示される | GET /api/v1/compliance/score-history | 過去の RuleEvaluationLog を集計 |

### 検証ポイント
- /triage-nda が NDA の 4 観点（相互性・期間・除外規定・守秘義務範囲）を正しく評価するか
- REQUIRED_CONTRACT ルールが物件単位で必須契約を正しくチェックするか
- コンプライアンススコアの計算ロジックが正しいか

---

## ペルソナ3: 中村太郎（建設業専門税理士）
### シナリオ: 士業ダッシュボード・顧問先横断管理

**前提条件**: STプランでログイン済み（士業アカウント） / 複数の顧問先 Account と紐づけ済み

| # | 操作 | 期待結果 | API | 備考 |
|---|------|---------|-----|------|
| 1 | ログイン → 士業ダッシュボードを開く | 顧問先一覧とそれぞれの ConPass スコアが表示される | GET /api/v1/advisor/dashboard | 複数 Account のスコアを横断取得 |
| 2 | 顧問先「山田建設株式会社」のスコアをクリック | 山田建設のコンプライアンスサマリが表示される。直近の期限アラート・RED 項目が表示される | GET /api/v1/compliance/summary?account_id={id} | account_id でフィルタ |
| 3 | /brief topic で「建設業法改正 2026年」を入力 | 建設業法改正の要点ブリーフが返る。影響を受ける顧問先の契約一覧が表示される | POST /api/v1/legal/brief | RAG で法令データベースを参照 |
| 4 | ブリーフ結果から「山田建設の工事請負契約」を選択 | 改正法に照らした条項の適合チェック結果が表示される | POST /api/v1/legal/review-contract | TenantRule(LAW_UPDATE) と連携 |
| 5 | 顧問先横断で「期限30日以内の契約」を検索 | 全顧問先の期限30日以内の契約が一覧表示される。顧問先名・契約名・期限日がソート可能 | GET /api/v1/advisor/expiring-contracts | 横断検索 API |
| 6 | 顧問先「佐藤不動産管理」のコンプライアンスレポートをPDFエクスポート | レポートPDFがダウンロードされる。スコア・アラート・推奨アクション一覧が含まれる | GET /api/v1/compliance/report/export | PDF 生成（pdfkit） |
| 7 | 「全顧問先のアラートサマリ」を表示 | 顧問先別のアラート件数（INFO/WARNING/CRITICAL）がマトリクス表示される | GET /api/v1/advisor/alert-summary | RuleEvaluationLog の severity 別集計 |

### 検証ポイント
- 士業アカウントが複数 Account のデータを横断参照できるか（権限制御）
- /brief が法令データベースを正しく検索し、関連契約を特定できるか
- 顧問先横断検索のパフォーマンスが実用的か

---

## ペルソナ4: 税理士事務所（STプラン移行）
### シナリオ: オンボーディング・Playbook設定・TenantRule構成

**前提条件**: 新規登録後、STプランへのアップグレードが完了した直後

| # | 操作 | 期待結果 | API | 備考 |
|---|------|---------|-----|------|
| 1 | STプラン契約完了 → 初回ログイン | オンボーディングウィザードが表示される。業種選択画面が出る | - | フロントエンド遷移 |
| 2 | 業種「税理士事務所」を選択 | 税理士事務所向け PlaybookTemplate の説明が表示される | GET /api/v1/playbooks/templates/?industry=ACCOUNTANT | PlaybookTemplate フィルタ |
| 3 | 「税理士事務所テンプレート」を適用 | TenantPlaybook が作成され、デフォルトの ClausePolicy が 12 種別分生成される | POST /api/v1/playbooks/ + POST /api/v1/playbooks/{id}/apply-template | テンプレート適用 API |
| 4 | ClausePolicy 一覧を確認 | 12 種別の条項ポリシーが表示される。各ポリシーに GREEN/YELLOW/RED の基準が設定されている | GET /api/v1/playbooks/{id}/clause-policies/ | ClausePolicy 一覧取得 |
| 5 | 「損害賠償・責任制限」ポリシーを編集 | standard_position を「上限: 契約金額の100%」から「上限: 報酬総額の200%」に変更できる | PUT /api/v1/playbooks/{id}/clause-policies/{cp_id}/ | ClausePolicy 更新 |
| 6 | TenantRuleSet を作成し、ルールを追加 | EXPIRY_ALERT（90日前）と REQUIRED_CONTRACT（顧問契約必須）の 2 ルールが登録される | POST /api/v1/rule-sets/ + POST /api/v1/rules/ | TenantRuleSet + TenantRule 作成 |
| 7 | ルール動作確認: テスト契約を登録し、期限を 80日後に設定 | EXPIRY_ALERT ルールが WARN を返し、ダッシュボードにアラートが表示される | POST /api/v1/rules/evaluate | RuleEvaluationLog が生成される |
| 8 | 顧問先を 3社登録し、各社に顧問契約を紐づけ | REQUIRED_CONTRACT ルールが全社 PASS を返す | POST /api/v1/rules/evaluate | 全社 PASS 確認 |
| 9 | 1社の顧問契約を削除 | REQUIRED_CONTRACT ルールが該当社で FAIL を返し、アラートが表示される | DELETE + POST /api/v1/rules/evaluate | FAIL 検出確認 |

### 検証ポイント
- PlaybookTemplate 適用で ClausePolicy が正しく 12 種別生成されるか
- ClausePolicy のカスタマイズが永続化されるか
- TenantRule の EXPIRY_ALERT と REQUIRED_CONTRACT が正しく動作するか
- ルール評価結果が RuleEvaluationLog に記録されるか

---

## ペルソナ5: 弁護士事務所（定型回答・エスカレーション）
### シナリオ: DSR対応・エスカレーション検知

**前提条件**: STプランでログイン済み / PlaybookTemplate「弁護士事務所」適用済み / ResponseTemplate 設定済み

| # | 操作 | 期待結果 | API | 備考 |
|---|------|---------|-----|------|
| 1 | /respond DSR で「個人データ開示請求」を入力 | ResponseTemplate(DSR) に基づく定型回答ドラフトが生成される。変数部分（請求者名・回答期限等）がプレースホルダで表示される | POST /api/v1/legal/respond | ResponseTemplate + TemplateVariable |
| 2 | テンプレート変数を埋める（請求者名: 田中一郎、期限: 30日） | 完成した回答文書が表示される。法定期限（30日以内）の妥当性チェック結果も表示される | - | フロントエンド処理 |
| 3 | エスカレーション検知: 請求内容に「訴訟予告」が含まれる場合 | escalation_triggers に「訴訟予告」がマッチし、「弁護士確認必須」のアラートが表示される | POST /api/v1/legal/respond | escalation_triggers チェック |
| 4 | 訴訟ホールド対応: /respond HOLD で訴訟ホールド通知を作成 | 訴訟ホールド通知のドラフトが生成される。保全対象文書の範囲が自動提案される | POST /api/v1/legal/respond | ResponseTemplate(HOLD) |
| 5 | 保全対象契約の一覧を確認 | 関連契約（相手方・期間でフィルタ）が一覧表示される | GET /api/v1/contracts/?client={id} | 契約検索 API |
| 6 | コンプライアンスダッシュボードで「未回答DSR」を確認 | 未回答のDSRリクエスト一覧と残り回答日数が表示される | GET /api/v1/compliance/pending-responses | 期限管理 |
| 7 | 回答済みDSRのステータスを「完了」に更新 | ステータスが更新され、コンプライアンススコアに反映される | PUT /api/v1/legal/responses/{id}/status | スコア再計算 |

### 検証ポイント
- ResponseTemplate の変数展開が正しく動作するか
- escalation_triggers のパターンマッチが正確か（偽陽性・偽陰性）
- 訴訟ホールドで関連契約が正しく特定されるか
- DSR 回答期限の法定期間チェックが正しいか

---

## 共通テスト項目

### 認証・認可
| # | テスト項目 | 期待結果 |
|---|-----------|---------|
| 1 | 未認証状態で API アクセス | 401 Unauthorized |
| 2 | 他テナントのデータにアクセス | 403 Forbidden または 404 Not Found |
| 3 | JWT トークン期限切れ後のアクセス | 401 Unauthorized + リフレッシュ案内 |
| 4 | ADMIN 権限でのみアクセス可能な API に ACCOUNT ユーザーでアクセス | 403 Forbidden |

### データ整合性
| # | テスト項目 | 期待結果 |
|---|-----------|---------|
| 1 | PlaybookTemplate 適用後に ClausePolicy を個別編集 → 再度テンプレート適用 | 既存の ClausePolicy が上書きされる旨の確認ダイアログが表示される |
| 2 | TenantRule 削除後の RuleEvaluationLog | ログは残存（CASCADE ではなく SET_NULL 相当の振る舞い） |
| 3 | Account 削除時の Playbook 関連データ | CASCADE で全削除される |

### パフォーマンス
| # | テスト項目 | 期待結果 |
|---|-----------|---------|
| 1 | 100 件の契約がある Account で /review-contract 実行 | 30 秒以内にレスポンス |
| 2 | 10 顧問先 x 50 契約の横断検索 | 10 秒以内にレスポンス |
| 3 | コンプライアンススコア算出（50 ルール x 100 契約） | 60 秒以内に完了 |
