# ConPass AI エージェント 技術要件定義書

**対象ブランチ**: `poc/rag-pipeline-tuning`
**対象リポジトリ**: `conpass-backend`（Push 済み: PR #546）、`conpass-agent-backend`（Push 予定）
**作成日**: 2026-03-02

---

## 目次

1. [法令管理基盤](#1-法令管理基盤)
2. [法令×契約書クロス検索](#2-法令契約書クロス検索)
3. [適法性チェック＋コンプライアンス状況サマリー](#3-適法性チェックコンプライアンス状況サマリー)
4. [契約書テンプレートエンジン](#4-契約書テンプレートエンジン)
5. [フィードバック収集](#5-フィードバック収集)
6. [RAG Pipeline チューニング（日本語チャンキング改善）](#6-rag-pipeline-チューニング日本語チャンキング改善)
7. [契約書本文テーブル構造保持](#7-契約書本文テーブル構造保持)

---

## 1. 法令管理基盤

### 主なユースケース

- 管理者が取適法・廃掃法・下請法などの法令テキストをシステムに登録する
- 法令改正時に既存インデックスを再作成して最新条文を即時反映する
- 登録済み法令の一覧・ステータス（インデックス済み／処理待ち）を確認する

### 現在の問題

AI エージェントが法令条文を参照する手段がなく、法令に関する回答は学習データに依存した不確かなものになっている。法令改正への追随も手動対応が必要であり、継続運用のコストが高い。

### 期待する効果

- 管理者が PDF またはテキストをアップロードするだけで、AI が自動的に条文単位でベクトルインデックスを生成する
- 法令改正時は「再インデックス」操作のみで即時反映できる
- 機能2（法令×契約書クロス検索）・機能3（適法性チェック）の前提基盤として機能する

### 実装内容

#### conpass-backend（Push 済み）

| コンポーネント | 内容 |
|---|---|
| `LawDocument` モデル | `law_name`, `law_short_name`, `law_number`, `effective_date`, `text`, `status`（PENDING / INDEXED / FAILED）, `article_count` |
| `LawFile` モデル | 添付ファイル（PDF等）のパス管理 |
| CRUD API | `GET/POST /api/setting/law/list`（一覧・アップロード）、`DELETE /api/setting/law/<id>`（削除）、`POST /api/setting/law/<id>/reindex`（再インデックス） |
| マイグレーション | 0080（LawDocument）、0081（LawFile）、0082（LawFile パス変更）、0083（LawDocument 検索キーワード） |
| 設定追加 | `AGENT_INTERNAL_URL`（Django→Agent 内部通信用） |

#### conpass-agent-backend（Push 予定）

| コンポーネント | 内容 |
|---|---|
| 内部 API | `POST /api/internal/law/ingest`（インジェスト）、`DELETE /api/internal/law/<law_id>`（削除） |
| チャンキング | 段落区切り（`\n{2,}`）で分割、最大 1,500 文字 / チャンク、超過時は 1,400 文字単位で強制分割 |
| 条文番号抽出 | 正規表現で「第 X 条（の X）」を抽出してペイロードに付与 |
| Qdrant | コレクション名: `conpass_laws`、Dense（384 次元 COSINE）+ Sparse（BM25）のハイブリッド構成 |
| ペイロード | `law_id`, `law_name`, `law_short_name`, `law_number`, `effective_date`, `article_number`, `chunk_index`, `text` |
| 冪等性 | 再インデックス時は `law_id` で既存ポイントを全削除してから再登録 |
| バッチ処理 | `UPSERT_BATCH_SIZE=50`（Qdrant 32 MB ペイロード上限対応） |

---

## 2. 法令×契約書クロス検索

### 主なユースケース

- 「取適法に影響を受ける契約の一覧を条文とともに表示して」
- 「下請法の観点から問題になりうる契約はどれか」
- 「〇〇法に関連する契約を全件ピックアップして」

### 現在の問題

法令と契約書を横断的に照合する手段がなく、AI は自己の学習データ頼みの不確かな法令解釈で回答してしまう。特定の法令要件を満たしていないリスクがある契約を事前に把握する方法がない。

### 期待する効果

- 登録済み法令の条文と全契約書をクロス検索し、法令要件上リスクのある契約を HIGH / MEDIUM に分類して一覧表示する
- AI が自己知識で法令解釈することを禁止し、常にシステム登録情報のみを根拠とする
- ユーザーは「監督機関・取引先から指摘される可能性がある契約」を事前に把握できる

### 実装内容

#### conpass-agent-backend（Push 予定）

**処理パイプライン（5 ステップ）**

| ステップ | 内容 |
|---|---|
| Step 1 | `conpass_laws` をハイブリッド検索（threshold 0.30）で関連条文を取得。補完クエリ（「委託契約 記載事項 義務」等）を並行実行して条文カバレッジを拡大 |
| Step 2 | 取得した条文テキストで `conpass_contracts` をセマンティック検索（threshold 0.40）。候補契約を最大 15 件に絞る |
| Step 3 | 各候補契約の複数チャンク（冒頭 + 中盤）を取得して文脈を確保 |
| Step 4 | 各候補契約 × 関連条文を `gpt-4o-mini` で並列 LLM 評価。出力: `ComplianceEvaluation { risk_level, gaps[], summary }` |
| Step 5 | HIGH / MEDIUM のみフィルタリングして返却（COMPLIANT は除外） |

**主要定数**

| 定数名 | 値 | 意図 |
|---|---|---|
| `LAW_SCORE_THRESHOLD` | 0.30 | 見逃し防止のため低めに設定 |
| `CONTRACT_SCORE_THRESHOLD` | 0.40 | 広めに候補取得してLLMで絞り込む |
| `MAX_CANDIDATE_CONTRACTS` | 15 | LLM 並列評価の上限 |
| `MIN_ARTICLE_LEN` | 50 文字 | 短い断片・条文参照のみのチャンクを除外 |

**関連ファイル**

- `app/services/chatbot/tools/law_search/law_search_tool.py`（1,242 行）
- `app/services/chatbot/tools/law_search/language_detect.py`（法令の言語・管轄検出）
- `app/services/chatbot/tools/law_search/checkpoints.py`（JSON チェックポイントローダー）

**システムプロンプト対応（jp_v5 / en_v6 に追加）**

- 法令に関する質問では必ず `law_search_tool` を呼び出す（AI の自己知識による法令回答を明示禁止）
- 「〇〇法に影響を受ける契約」の背後にあるコンプライアンスリスク確認の意図を AI が理解して回答する
- ツール結果は全件・根拠条文つきで表示することを義務化
- フォローアップ質問時は `read_contracts_tool` で原文を取得する（架空の法的理由の生成を禁止）

---

## 3. 適法性チェック＋コンプライアンス状況サマリー

### 主なユースケース

- 「廃掃法の観点でこの産業廃棄物処理委託契約をチェックして」
- 「コンプライアンス状況のサマリーを教えて」
- 「契約 #37 のコンプライアンススコアは？」
- 「スコアが低い契約はどれか」

### 現在の問題

個別契約が特定法令の要件を満たしているかの確認を人手で行っており、抜け漏れが生じやすい。全体のコンプライアンス状況も一覧で把握できないため、経営・法務への報告にコストがかかる。

### 期待する効果

- 既知の法令（廃掃法・リース・取引）は JSON チェックポイントルールエンジンで高速・高精度に評価する
- 未登録法令は LLM が条文テキストから自動評価するフォールバックを提供する
- HIGH / MEDIUM / LOW / COMPLIANT のリスクレベルと具体的なギャップ（何が不足か）を返却する
- アカウント全体のコンプライアンス状況（平均スコア・分布・要注意契約リスト）を即時取得できる

### 実装内容

#### チェックポイント JSON ルールエンジン

**対象法令（3 件）**

| ファイル | 法令 | チェックポイント数 |
|---|---|---|
| `checkpoints/haiso.json` | 廃棄物の処理及び清掃に関する法律（廃掃法） | 10 件（HAISO-01〜10） |
| `checkpoints/lease.json` | リース関連法令 | — |
| `checkpoints/tori.json` | 取引関連法令 | — |

**チェックポイントの構造**

各チェックポイントは以下のフィールドを持つ:

| フィールド | 内容 |
|---|---|
| `id` | チェックポイント ID（例: `HAISO-01`） |
| `requirement` | 法令が求める要件の要約 |
| `legal_basis` | 根拠条文（例: 施行令第 6 条の 2 第 1 号） |
| `default_severity` | デフォルトリスクレベル（HIGH / MEDIUM / LOW） |
| `absence_is_risk` | 条項が存在しない場合をリスクとみなすか |
| `compliant_patterns` / `compliant_keywords` | 適合を示す文言・パターン |
| `violation_patterns` / `violation_keywords` | 違反を示す文言・パターン |

**新しい法令の追加方法**: `checkpoints/` ディレクトリに JSON ファイルを追加するだけでコード変更不要（`checkpoints.py` が起動時に自動読み込み）

#### LLM 評価

- チェックポイント未定義の法令は `gpt-4o-mini` で評価（フォールバック）
- 出力スキーマ:
  - `ComplianceGap`: `{ article_number, requirement, gap_description, contract_reference }`
  - `ComplianceEvaluation`: `{ risk_level: HIGH|MEDIUM|LOW|COMPLIANT, gaps[], summary }`
- 評価優先度: ①文書種別確認（身分証明書・請求書等は除外）→ ②必須記載事項確認 → ③禁止行為確認

#### コンプライアンス状況サマリー

`get_compliance_summary()` / `check_contract_compliance()` ツールをオーケストレーターに直接登録（サブエージェントへのルーティング不要）:

| 関数 | 返却内容 |
|---|---|
| `get_compliance_summary(account_id)` | 契約総数、平均スコア、スコア分布（high: 80+, medium: 60-79, low: 40-59, critical: <40）、要注意契約リスト |
| `check_contract_compliance(contract_id, contract_body)` | コンプライアンススコア（0-100）、問題リスト（severity + description） |

**スコア算出ロジック**: 基準 100 点 − HIGH × 20 − MEDIUM × 10 − LOW × 5

#### リスク分析への法令適合チェック統合

- `perform_law_compliance_check(contract_body, related_laws)`: 契約書本文と関連法令条文を GPT-4o で比較し、問題リスト `[{law_name, article, issue, severity}]` を返却
- `prompts.py` に `LAW_COMPLIANCE_CHECK_PROMPT_TEMPLATE` を追加

**関連ファイル**

- `app/services/chatbot/tools/law_search/checkpoints/` （JSON ファイル群）
- `app/services/chatbot/tools/law_search/checkpoints.py`
- `app/services/chatbot/tools/compliance/compliance_tool.py`
- `app/services/chatbot/tools/risk_analysis/perform_analysis.py`
- `app/services/chatbot/tools/risk_analysis/prompts.py`
- `app/services/chatbot/tools/risk_analysis/risk_analysis_tool.py`
- `app/services/chatbot/agents/orchestrator_agent.py`

---

## 4. 契約書テンプレートエンジン

### 主なユースケース

- 「この業務委託契約書を業界標準テンプレートと比較して」
- 「IT 業界の SLA テンプレートはどれがある？」
- 「契約 #42 の条項は標準条件から乖離しているか？」

### 現在の問題

相手先から受け取った契約書が自社の標準条件・業界基準から乖離していても自動で検出する手段がなく、レビューを法務担当者が都度人手で行っている。比較の品質・スピードにばらつきが生じている。

### 期待する効果

- 業界・契約タイプ別のテンプレートを一覧表示し、適切なテンプレートを選択できる
- 契約書とテンプレートを条項単位で自動比較し、GREEN（標準的）/ YELLOW（要確認）/ RED（大幅乖離）でリスクを可視化する
- 法務担当者のレビュー工数を削減し、要確認箇所への集中を支援する

### 実装内容

#### conpass-agent-backend（Push 予定）

| コンポーネント | 内容 |
|---|---|
| `template_list(industry, contract_type)` | 業界・契約タイプでフィルタリング可能なテンプレート一覧を返却。各テンプレートに `template_id`, `template_type`, `industry`, `description`, `clause_list` を含む |
| `template_compare(contract_id, template_type)` | 指定契約とテンプレートを条項単位で比較し、GREEN / YELLOW / RED ラベルと判定理由を返却 |
| `TemplateService` | テンプレートの管理・マッチングロジック |
| ツール登録 | `get_template_list_tool()`, `get_template_compare_tool()` として AI エージェントに登録 |

**関連ファイル**

- `app/services/chatbot/tools/template_compare_tool.py`
- `app/services/templates/template_service.py`

---

## 5. フィードバック収集

### 主なユースケース

- チャットの検索結果・AI 回答に対してユーザーが 👍 / 👎 を送信する
- 不正確な回答に対してコメントを添えて報告する
- ツール別・クエリ別の精度を分析して改善サイクルに活用する

### 現在の問題

AI 回答の品質に関するユーザー評価データが蓄積されておらず、どのツール・クエリで精度が低いかを定量的に把握できない。改善施策の効果検証も困難な状態にある。

### 期待する効果

- チャット単位・メッセージ単位・ツール単位でユーザー評価を記録する
- `session_id` + `message_id` による粒度の細かい分析で、改善が必要な箇所を特定できる
- フィードバックデータを将来のモデルファインチューニングやプロンプト改善に活用できる

### 実装内容

#### conpass-agent-backend（Push 予定）

| コンポーネント | 内容 |
|---|---|
| エンドポイント | `POST /api/v1/feedback` |
| リクエスト | `session_id`（必須）、`message_id`（必須）、`rating`（`thumbs_up` \| `thumbs_down`、必須）、`comment`（任意）、`tool_used`（任意）、`result_contract_ids`（任意） |
| レスポンス | `{ status: "success", feedback_id: "<UUID v4>" }` |
| 保存先 | Firestore `chat_feedback` コレクション |
| 認証 | ConPass JWT トークン必須（ヘッダーから `user_id` を抽出して自動付与） |
| 自動付与フィールド | `feedback_id`（UUID v4）、`user_id`、`created_at`（UTC ISO 形式） |

**関連ファイル**

- `app/api/v1/feedback.py`
- `app/schemas/feedback.py`

---

## 6. RAG Pipeline チューニング（日本語チャンキング改善）

### 主なユースケース

- 「第 5 条の秘密保持義務について説明して」のような条文単位の参照
- 「(2) の免責事項はどう書いてある？」のような項・号単位の参照
- 料金表・SLA 等、表形式の条件が含まれる契約の検索

### 現在の問題

固定長チャンキングでは第 X 条の条文が任意の位置で分断され、条文の意味的完全性が失われて検索精度が低下する。条番号・節タイトルがチャンクに含まれないため AI が条文を正確に特定できない。また日本語形態素の途中で切断されると意味が変わる場合がある。

### 期待する効果

- 法的構造（条・項・号）の境界でチャンクを分割し、条文の意味的完全性を保持する
- 各チャンクに `article_number` / `clause_number` / `section_title` のメタデータを付与し、条文の追跡可能性を向上させる
- SudachiPy による形態素境界分割でトークンの途中切断を防止する

### 実装内容

#### conpass-agent-backend（Push 予定）

**2 層チャンキング戦略**

| 層 | 内容 |
|---|---|
| Tier 1（構造分割） | 「第 X 条」「第 X 項」「(X)」「①②」等の法的構造パターンで分割。全角数字・漢数字を半角に正規化して条文番号を統一。各チャンクに `article_number`, `clause_number`, `section_title` を付与 |
| Tier 2（形態素分割） | Tier 1 チャンクが `chunk_size` を超える場合、SudachiPy で文境界（句点）→ 節境界（読点）→ トークン境界の優先順で再分割。SudachiPy 未インストール時は全位置をトークン境界とみなすフォールバックを使用 |

**SudachiPy の活用**

- 形態素解析で日本語の正確な単語境界を認識し、格助詞・述語などの中途切断を防止
- `split_mode=C`（複合語を最小分割）で検索精度を向上

**正規化パターン**

| 対象 | 変換 |
|---|---|
| 全角数字 | ０-９ → 0-9 |
| 漢数字 | 一〜九、十、百 → 1〜9、10、100 |
| 条番号 | `第([0-9０-９一二三四五六七八九十百]+)条` |
| 項番号 | `第X項` / `X.` |
| 号番号 | `(X)` / `①-⑳` |

**関連設定変更**

| ファイル | 変更内容 |
|---|---|
| `app/core/model_settings.py` | `is_development()` による dev / prod LLM 設定分岐（dev: `effort=medium`、prod: 別設定） |
| `app/core/environment_flags.py` | `is_multi_agent_enabled()` フラグ追加 |
| `app/main.py` | 起動時に Firestore からフィーチャーフラグ・正規化辞書を読み込む |
| `.env.example` | PoC 全機能の環境変数を追加（`RRF_K`, `MULTI_AGENT_ENABLED`, `LAW_QDRANT_COLLECTION` 等） |

**関連ファイル**

- `cloud/cloud_run/generate_embeddings/chunker.py`
- `cloud/cloud_run/generate_embeddings/pipeline.py`
- `cloud/cloud_run/generate_embeddings/metadata_map.py`
- `cloud/cloud_run/generate_embeddings/model.py`
- `cloud/cloud_run/generate_embeddings/doc_generator.py`
- `cloud/cloud_run/generate_embeddings/qdrant_indexes.py`
- `cloud/cloud_run/generate_embeddings/requirements.txt`

---

## 7. 契約書本文テーブル構造保持

### 主なユースケース

- 「この契約の料金表を確認して」のような表形式の条件参照
- 「月額費用はいくらか」のように料金表から値を抽出する検索
- 仕様書・SLA 等、表形式で定義された条件を含む契約の適法性チェック

### 現在の問題

契約書の HTML を保存・インデックス化する際に `strip_tags` で `<table>` を丸ごと削除してしまうため、料金表・仕様表・対照表の内容がベクトル DB に格納されない。AI が表の内容を参照できず、回答精度が低下する。

### 期待する効果

- HTML の `<table>` を Markdown テーブル形式（`| 列1 | 列2 |`）に変換してから保存・インデックス化することで、表の構造と内容が検索・参照可能になる
- AI が料金表・仕様表の内容を正確に回答できるようになる
- 適法性チェックにおいても、表形式で記載された委託料金・処理能力等を正しく評価できる

### 実装内容

#### _tables_to_markdown() の処理内容

1. BeautifulSoup で HTML をパース
2. 全 `<table>` 要素を走査してヘッダー行（`<th>`）と データ行（`<td>`）を抽出
3. Markdown テーブル形式（`| col1 | col2 |`）に変換。ヘッダー行直後に区切り行（`| --- | --- |`）を挿入
4. パイプ文字（`|`）は全角（`｜`）にエスケープして Markdown テーブルの構造を保護
5. 変換後に `strip_tags` で残りの HTML タグを除去

#### 適用箇所（3 パス）

| ファイル | 適用タイミング |
|---|---|
| `contract_service.py` `save_body()` | 契約書を画面から保存・更新するとき |
| `contract_upload_prediction_task.py` `create_contract_body()` | PDF アップロード後の OCR 処理パス（GV-OCR / 非 GV-OCR 両方） |
| `contract_ingest.py` `_html_to_text()` | Webhook 経由で AI エージェントが契約書をインデックス化するとき |

**関連ファイル**

- `app/conpass/services/contract/contract_service.py`（conpass-backend、Push 済み）
- `app/conpass/services/contract/contract_upload_prediction_task.py`（conpass-backend、Push 済み）
- `app/api/internal/contract_ingest.py`（conpass-agent-backend、Push 予定）

---

## 付録：コンポーネント間の関係

```
[管理者]
  │ 法令 PDF / テキストをアップロード
  ↓
[conpass-backend] POST /api/setting/law/upload
  │ pdfminer でテキスト抽出 → LawDocument 保存
  ↓
[conpass-agent-backend] POST /api/internal/law/ingest     ← 機能1
  │ 段落チャンク化 → Dense + Sparse Embedding
  └→ Qdrant: conpass_laws コレクションへ UPSERT

[ユーザー]「取適法に影響を受ける契約は？」
  ↓
[Orchestrator Agent]
  ├→ law_search_tool（機能2）
  │    Step1: conpass_laws ハイブリッド検索（閾値 0.30）
  │    Step2: conpass_contracts セマンティック検索（閾値 0.40）
  │    Step3: gpt-4o-mini で LLM 評価 → HIGH/MEDIUM のみ返却
  │
  ├→ law_search_tool + checkpoints.py（機能3）
  │    廃掃法/リース/取引: JSON ルールエンジン
  │    その他: LLM フォールバック評価
  │    出力: ComplianceEvaluation { risk_level, gaps[], summary }
  │
  ├→ template_compare_tool（機能4）
  │    契約書 × テンプレート → GREEN/YELLOW/RED
  │
  └→ get_compliance_summary_tool（機能3）
       全契約スコア分布 + 要注意契約リスト

[ユーザー]「この回答は役立った？」
  ↓
[conpass-agent-backend] POST /api/v1/feedback             ← 機能5
  └→ Firestore: chat_feedback コレクションへ保存

[Cloud Run Embedding Pipeline]                            ← 機能6
  契約書テキスト
  → Tier1（条/項/号 境界分割）
  → Tier2（SudachiPy 形態素境界分割）
  → article_number / clause_number / section_title メタデータ付与
  → Qdrant: conpass_contracts コレクションへ UPSERT
```
