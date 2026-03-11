# RAGソース稼働状況レポート

生成日時: 2026-02-21 (タスク#30 関連契約書RAG統合・orchestratorツール追加 完了時点)

## サマリー

- 実装済み: 6 / 9 ソース
- 稼働確認待ち（データ投入要）: 3 / 9 ソース

## 各ソース詳細

| ソース | 説明 | ステータス | 実装状況 |
|--------|------|-----------|---------|
| contracts | 契約書（メインソース） | 稼働中 | Qdrantメインコレクション（31,702 chunks） |
| law_regulations | 法令規制（BE3実装） | 実装済み | e-Gov API連携 + Cloud Run egov_law_fetcher + 専用コレクション |
| contract_templates | 契約テンプレート（BE4実装） | 実装済み | template_service.py + source_type=template + 5業種テンプレート |
| related_contracts | 関連契約書 | 実装済み | related_contract メタデータフィールド + 2段階RAG検索 |
| metadata_index | メタデータインデックス | 稼働中 | Qdrantペイロードフィールド（OCR confidence_score対応済み） |
| ocr_results | OCR結果 | 実装済み | source_type=ocr + confidence_score正規化（BE5実装） |
| benchmark_data | ベンチマークデータ | 実装済み | benchmark_service.py + Redis 1h TTL キャッシュ（BE4実装） |
| user_feedback | ユーザーフィードバック | データ投入待ち | Firestoreコレクション未投入 |
| expert_knowledge | 専門家知見 | データ投入待ち | source_type=expert_knowledge（データ投入パイプライン未構築） |

## MS1 実装で追加されたソース

### 1. law_regulations（法令規制）
- **実装**: `cloud/cloud_run/egov_law_fetcher/`
  - `main.py`: 民法・商法・建設業法・宅建業法・労基法・個人情報保護法の6法令取得
  - `law_parser.py`: 編>章>節>条の階層XMLパーサー
  - `change_detector.py`: SHA-256ハッシュによる改正検知
  - `scheduler_config.yaml`: Cloud Scheduler AM6:00 JST設定
- **Embedding**: `cloud/cloud_run/generate_embeddings/` の law_regulation パイプライン
  - 256文字の条文単位チャンキング
  - `law_regulations` 専用Qdrantコレクションに格納
- **検索**: `semantic_search_tool.py` の `include_law_regulations=True` パラメータ
- **コンプライアンス評価**: `risk_analysis_tool.py` の `_check_law_compliance()`

### 2. contract_templates（契約テンプレート）
- **実装**: `app/services/templates/template_service.py`
- **5業種テンプレート**: 秘密保持・業務委託・売買・ライセンス・システム開発
- **API**: `GET /api/v1/template/list`, `GET /api/v1/template/compare`, `POST /api/v1/template/seed`

### 3. related_contracts（関連契約書）
- **実装**: `semantic_search_tool.py` の `_fetch_related_contracts()`
- **2段階RAG**: 1次検索結果の `related_contract` メタデータからフォロー検索
- **デフォルト有効**: `include_related_contracts=True`（`semantic_search()` のデフォルト引数）

### 4. benchmark_data（ベンチマークデータ）
- **実装**: `app/services/benchmark/benchmark_service.py`（BE4実装）
- **エージェント統合**: `app/services/chatbot/tools/benchmark_tool.py`
  - `benchmark_stats`: 業界・契約種別ごとの統計（期間中央値、支払条件、責任上限、自動更新率）
  - `benchmark_compare`: 特定契約と業界平均の乖離度分析
- **キャッシュ**: Redis 1時間TTL

### 5. ocr_results（OCR結果）
- **実装**: `app/services/ocr_service.py` の `get_normalized_confidence()`
- **正規化**: Tesseract(0-100) / Document AI(0.0-1.0) を統一0.0-1.0スケールに
- **レビューキュー**: `app/api/v1/metadata_crud/review_queue.py` で低confidence契約を管理

## Orchestratorツール追加（MS1）

オーケストレーターに以下のツールを追加（`app/services/chatbot/agents/orchestrator_agent.py`）:

| ツール名 | 機能 |
|---------|------|
| `get_compliance_summary` | アカウント全体のコンプライアンスサマリー照会 |
| `check_contract_compliance` | 契約1件のコンプライアンススコア算出（0-100） |

チャットから「コンプライアンス状況を教えて」と質問した際、サブエージェントルーティングなしで直接回答可能。

## エージェントツール登録（タスク#30）

`contract_and_document_intelligence_agent` の `get_assistant_tools()` に以下を追加:

| ツール名 | ソースファイル | 機能 |
|---------|-------------|------|
| `benchmark_stats` | `tools/benchmark_tool.py` | 業界ベンチマーク統計取得 |
| `benchmark_compare` | `tools/benchmark_tool.py` | 契約vs業界平均の乖離度比較 |
| `template_list` | `tools/template_compare_tool.py` | テンプレート一覧照会 |
| `template_compare` | `tools/template_compare_tool.py` | 契約vsテンプレートのGREEN/YELLOW/RED比較 |

## Cloud Runパイプライン検証結果（タスク#30 Section3）

### related_contracts のデータフロー

`related_contract` メタデータは **独立した source_type ではなく**、通常の契約書メタデータフィールドとしてQdrantペイロードに格納される。

**データフロー:**
1. `record_sync_handler.py` が MySQL `conpass_metadata` テーブルからメタデータを取得
2. `doc_generator.py` の `get_metadata()` が全メタデータをkey-value→Documentメタデータに変換
3. `pipeline.py` の `run_custom_pipeline()` が通常の契約書としてEmbedding・Qdrant格納
4. Qdrantペイロードに `related_contract` フィールドが含まれる（MySQLに登録されている場合）
5. `semantic_search_tool.py` の `_fetch_related_contracts()` がクエリ時にこのフィールドを読み取り2段階検索

**結論:** `record_sync_handler.py` の修正は不要。related_contractsは既存の契約書パイプラインで正しく処理されている。

## 改善アクション

停止中または未確認のソースについて:

- **user_feedback**: Firestoreの `user_feedback` コレクションにデータを投入する
- **expert_knowledge**: 専門家知見のデータ収集・ingestion パイプラインを構築する

## 実行方法

```bash
cd conpass-agent-backend
python -m scripts.check_rag_sources
```

スクリプト実行後、このファイルは自動的に最新の結果で上書きされます。
