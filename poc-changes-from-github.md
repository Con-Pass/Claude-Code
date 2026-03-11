# PoC 差分ドキュメント — GitHub main との比較

作成日: 2026-03-10
比較基準: GitHub `main` ブランチ (`ConPass-Nihon-Purple/conpass-agent-backend`, `conpass-backend`)

---

## 概要

| リポジトリ | 変更ファイル数 | 新規ファイル数 |
|-----------|-------------|-------------|
| `conpass-agent-backend` | 41 | 27 |
| `conpass-backend` | 14（M） / 41（未コミット） | 25（未コミット） |

---

## conpass-agent-backend

### 今回セッション（2026-03-09/10）の変更

日付フィルタ改善（Task #12）と数値集計機能（Task #13）の実装。

#### 変更ファイル

| ファイル | 変更種別 | 変更内容 |
|---------|---------|---------|
| `app/services/chatbot/tools/metadata_search/filter_converter.py` | CHANGED | `_DATE_EPOCH_FIELDS` 定数・`_iso_to_epoch()` 関数を追加。`process_condition()` 内で日付フィールドの RangeCondition キーを `*_epoch` に書き換え、値を ISO 文字列から epoch float に変換。+33行 |
| `app/services/chatbot/tools/tools.py` | CHANGED | `get_aggregate_contracts_tool` のインポート・登録追加。`benchmark_tool`, `template_compare_tool`, `law_search_tool` を `get_assistant_tools` にも追加。+14行 |
| `app/api/internal/contract_ingest.py` | NEW (本リポには存在しない) | `datetime/timezone` インポート追加。`_DATE_LABELS` 定数・`_date_to_epoch()` 関数追加。インジェスト時に `*_epoch` float フィールドを追加書き込み |
| `scripts/local_ingest.py` | NEW (本リポには存在しない) | epoch 変換ロジック追加（`contractdate`, `contractstartdate`, `contractenddate`, `cancelnotice`）。`ensure_payload_indexes()` に float インデックス 4件追加 |

#### 新規ファイル

| ファイル | 内容 |
|---------|------|
| `app/services/chatbot/tools/metadata_search/aggregate_tool.py` | 数値集計 LlamaIndex FunctionTool。Django API `GET /contract/metadata/aggregate` を呼び出し、件数・合計・平均・グループ別集計を返す。`get_aggregate_contracts_tool(directory_ids, conpass_api_service)` ファクトリ関数 |
| `scripts/add_epoch_fields.py` | 既存 Qdrant ポイントに epoch フィールドをパッチするスクリプト（ベクトル再計算なし）。`--dry-run` オプション付き |

#### 変更背景

**問題**: Qdrant の `RangeCondition` は数値のみ有効。日付メタデータが ISO 文字列（`'2025-04-01'`）で保存されていたため、「来月末までに終了する契約」等の日付範囲フィルタが無効だった。

**解決**: Qdrant ペイロードに `*_epoch` float フィールドを追加。既存 65 ポイントは `add_epoch_fields.py` でパッチ済み。`filter_converter.py` が自動的に ISO 文字列 → epoch 変換してクエリに使用する。

---

### 過去セッションからの累積変更（GitHub main との全差分）

#### 変更ファイル（41件）

| カテゴリ | ファイル | 主な変更内容 |
|---------|---------|------------|
| **API ルーティング** | `app/api/router.py` | internal, compliance, feedback, template, benchmark ルーター追加 |
| **チャット v1** | `app/api/v1/chat_non_streaming.py` | ストリーミングなし応答エンドポイント更新 |
| **メタデータ CRUD** | `app/api/v1/metadata_crud/__init__.py` | エンドポイント整理 |
| | `app/api/v1/metadata_crud/create_metadata_key.py` | キー作成 API |
| | `app/api/v1/metadata_crud/delete_metadata_key.py` | キー削除 API |
| **設定** | `app/core/config.py` | QDRANT_LAWS_COLLECTION, 各種フラグ追加 |
| | `app/core/environment_flags.py` | フィーチャーフラグ管理 |
| | `app/core/middleware.py` | 認証ミドルウェア更新 |
| | `app/core/model_settings.py` | Reranker 等モデル設定追加 |
| | `app/main.py` | FastAPI アプリ初期化更新 |
| **スキーマ** | `app/schemas/chat.py` | セッション種別等追加 |
| | `app/schemas/metadata_crud.py` | CRUD スキーマ更新 |
| **エージェント** | `app/services/chatbot/agent_adapter.py` | セッション管理更新 |
| | `app/services/chatbot/agents/contract_and_document_intelligence_agent.py` | CDI エージェント改善 |
| | `app/services/chatbot/agents/metadata_control_plane_agent.py` | メタ制御エージェント |
| | `app/services/chatbot/agents/orchestrator_agent.py` | オーケストレーター更新 |
| | `app/services/chatbot/engine.py` | チャットエンジン更新 |
| **プロンプト** | `app/services/chatbot/prompts/system_prompts_en_v5.py` | EN プロンプト v5 |
| | `app/services/chatbot/prompts/system_prompts_jp_v3.py` | JP プロンプト v3 |
| | `app/services/chatbot/prompts/system_prompts_jp_v5.py` | JP プロンプト v5 |
| **ツール** | `app/services/chatbot/tools/fetch_file_content/fetch_file_content_tool.py` | GCS ファイル取得改善 |
| | `app/services/chatbot/tools/metadata_crud/*.py` (7件) | メタデータ CRUD ツール群 |
| | `app/services/chatbot/tools/metadata_search/filter_converter.py` | **今回セッション変更** |
| | `app/services/chatbot/tools/metadata_search/fuzzy_company_matcher.py` | ファジーマッチ改善 |
| | `app/services/chatbot/tools/metadata_search/qdrant_client.py` | クライアント更新 |
| | `app/services/chatbot/tools/metadata_search/text_to_qdrant_filters.py` | LLM→フィルタ変換改善 |
| | `app/services/chatbot/tools/risk_analysis/perform_analysis.py` | リスク分析改善 |
| | `app/services/chatbot/tools/risk_analysis/prompts.py` | リスク分析プロンプト |
| | `app/services/chatbot/tools/risk_analysis/risk_analysis_tool.py` | absence_is_risk 対応 |
| | `app/services/chatbot/tools/semantic_search/semantic_search_tool.py` | RRF/閾値チューニング |
| | `app/services/chatbot/tools/tools.py` | **今回セッション変更** |
| | `app/services/chatbot/tools/utils/document_store.py` | ドキュメントストア更新 |
| | `app/services/chatbot/workflows/multi_agent_workflow.py` | マルチエージェント更新 |
| **外部連携** | `app/services/conpass_api_service.py` | API メソッド追加 |
| | `app/services/ocr_service.py` | OCR サービス更新 |

#### 新規ファイル（27件）

| ファイル/ディレクトリ | 機能 |
|---------------------|------|
| `app/api/internal/` | Django Webhook 受信エンドポイント（contract_ingest, law_ingest） |
| `app/api/v1/benchmark.py` | RAG ベンチマーク API |
| `app/api/v1/compliance.py` | コンプライアンス評価 API |
| `app/api/v1/feedback.py` | フィードバック収集 API |
| `app/api/v1/legal_commands.py` | 法的コマンド API |
| `app/api/v1/template.py` | テンプレート API |
| `app/api/v1/metadata_crud/review_queue.py` | レビューキュー API |
| `app/schemas/feedback.py` | フィードバックスキーマ |
| `app/services/benchmark/` | ベンチマーク評価サービス |
| `app/services/chatbot/feature_flags.py` | フィーチャーフラグ |
| `app/services/chatbot/prompts/system_prompts_en_v6.py` | EN プロンプト v6 |
| `app/services/chatbot/tools/benchmark_tool.py` | ベンチマークツール |
| `app/services/chatbot/tools/compliance/` | コンプライアンスツール群 |
| `app/services/chatbot/tools/law_search/` | **法令検索ツール（今回 PoC）** |
| `app/services/chatbot/tools/metadata_search/aggregate_tool.py` | **数値集計ツール（今回セッション）** |
| `app/services/chatbot/tools/semantic_search/query_expander.py` | クエリ拡張 |
| `app/services/chatbot/tools/semantic_search/reranker.py` | Reranker |
| `app/services/chatbot/tools/semantic_search/search_cache.py` | 検索キャッシュ |
| `app/services/chatbot/tools/template_compare_tool.py` | テンプレート比較ツール |
| `app/services/compliance/` | コンプライアンスサービス群 |
| `app/services/connectors/` | 外部コネクタ |
| `app/services/contract_classifier.py` | 契約書分類サービス |
| `app/services/legal/` | 法務サービス群 |
| `app/services/templates/` | テンプレートサービス群 |
| `scripts/add_epoch_fields.py` | **Qdrant epoch パッチスクリプト（今回セッション）** |
| `scripts/check_rag_sources.py` | RAG ソース確認スクリプト |
| `scripts/local_ingest.py` | ローカル全件インジェストスクリプト |
| `scripts/local_law_ingest.py` | 法令ローカルインジェストスクリプト |

---

## conpass-backend

### 今回セッションの変更（未コミット）

| ファイル | 変更種別 | 変更内容 |
|---------|---------|---------|
| `app/conpass/urls.py` | CHANGED | `ContractMetaAggregateView` インポート追加。`contract/metadata/aggregate` パス登録（+2行）。その他 PoC 関連ルート追加（GMO Sign, Playbook, Compliance, Rescan, Law, Relation など） |
| `app/conpass/views/contract/aggregate_view.py` | NEW | 契約書メタデータ集計 API。`GET /api/contract/metadata/aggregate`。count/sum/avg + group_by + 日付範囲フィルタ対応。ディレクトリ権限チェック付き。154行 |

### 過去セッションからの累積変更（コミット済み + 未コミット）

#### 最新コミット
```
09a766bd fix: openaiとpdfminer-sixをPipfile.lockに追加  ← PR #552
```

#### 未コミット変更ファイル（git status: M = 変更済み, ?? = 未追跡）

**M (修正済み)**

| ファイル | 主な変更内容 |
|---------|------------|
| `app/conpass/urls.py` | 上記参照 |
| `app/conpass/views/contract/views.py` | Rescan, ExtractionStatus, Archive等追加 |
| `app/conpass/models/__init__.py` | LawDocument, LawFile, Playbook等モデル登録 |
| `app/conpass/tasks.py` | AI Agent 通知 Celery タスク追加 |
| `app/conpass/services/contract/contract_service.py` | AI 通知連携 |
| `app/conpass/services/contract/contract_upload_prediction_task.py` | OCR パイプライン改善 |
| `app/conpass/services/gcp/cloud_storage.py` | GCS 連携改善 |
| `app/conpass/services/growth_verse/gv_prediction.py` | GvPredict 更新 |
| `app/conpass/admin.py` | 新モデル admin 登録 |
| `functions/conpass-entity-extraction-gpt/prompt*.txt` | OCR エンティティ抽出プロンプト改訂 |
| `docker/*/Dockerfile` | Dockerfile 更新 |
| `.env.example`, `.gitignore` | 設定更新 |

**?? (新規未追跡)**

| ファイル/ディレクトリ | 内容 |
|---------------------|------|
| `app/conpass/views/contract/aggregate_view.py` | **数値集計 View（今回セッション）** |
| `app/conpass/views/contract/rescan_view.py` | OCR 再スキャン API |
| `app/conpass/views/contract/relation_view.py` | 関連契約書 API |
| `app/conpass/views/setting/law_view.py` | 法令管理 CRUD API |
| `app/conpass/views/compliance/` | コンプライアンス評価 View 群 |
| `app/conpass/views/gmo_sign/` | GMO Sign 連携 View 群 |
| `app/conpass/views/playbook/` | プレイブック管理 View 群 |
| `app/conpass/views/local_file_view.py` | ローカルファイル提供 View |
| `app/conpass/models/law_document.py` | 法令ドキュメントモデル |
| `app/conpass/models/law_file.py` | 法令ファイルモデル |
| `app/conpass/models/playbook.py` | プレイブックモデル |
| `app/conpass/models/gmo_sign.py` | GMO Sign モデル |
| `app/conpass/migrations/0079〜0083_*.py` | 上記モデルのマイグレーション |
| `app/conpass/services/gcp/vision_service_local_patch.py` | OCR ローカル fallback（**ローカル開発専用・PR 対象外**） |
| `app/conpass/services/gcp/local_storage_mock.py` | ローカルストレージモック |
| `app/conpass/services/playbook/` | プレイブックサービス群 |
| `app/conpass/services/gmo_sign/` | GMO Sign サービス群 |
| `app/conpass/mailer/compliance_alert_mailer.py` | コンプライアンスアラートメーラー |
| `functions/conpass-entity-extraction-gpt/prompt1.1.txt` | エンティティ抽出プロンプト v1.1 |

---

## Qdrant 変更（クラウド Cloud ID: 70895a47-011d-48f0-9855-6a033abe195d）

| コレクション | 変更内容 |
|------------|---------|
| `conpass` | epoch フィールド（4種）を既存 65 ポイントに追加済み（`add_epoch_fields.py` 実行済み）。全件再インデックス完了（78ポイント、28件） |

### 追加された Qdrant ペイロードフィールド

| フィールド名 | 型 | 内容 |
|------------|-----|------|
| `契約日_contract_date_epoch` | float | 契約日の Unix epoch 秒 |
| `契約開始日_contract_start_date_epoch` | float | 契約開始日の Unix epoch 秒 |
| `契約終了日_contract_end_date_epoch` | float | 契約終了日の Unix epoch 秒 |
| `契約終了日_cancel_notice_date_epoch` | float | 解約通知期限の Unix epoch 秒 |

---

## 注意事項

1. **`vision_service_local_patch.py`** はローカル開発専用。本番は GrowthVerse API を使用するため PR 対象外
2. **`conpass-agent-backend`** は現在 push 権限がないため、ローカルのみの変更
3. **`conpass-backend`** は PR #552（Pipfile.lock のみ）がマージ済み。上記 M/??ファイルは未 PR
