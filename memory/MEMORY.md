# ConPass プロジェクト メモリ

> このファイルは Claude Code の記憶です。別端末でも同じ文脈で作業を続けるために参照してください。

## プロジェクト構成

- **conpass-backend**: Django バックエンド
- **conpass-agent-backend**: FastAPI AI エージェント
- **conpass-frontend**: Vue.js フロントエンド

## BGE-M3 導入 (2026-03)

- モデル: `BAAI/bge-m3` — 1024次元 Dense + SPLADE Sparse のハイブリッド検索
- Qdrant コレクション: `conpass_bge_m3`（旧 `conpass` は廃止予定）
- 起動時に BGE-M3 ロードに約70秒かかる
- Payload indexes 必須: `contract_id` (INTEGER), `directory_id` (INTEGER), `private` (BOOL)
  - index がないと `must_not: [private=True]` フィルタが 400 エラー

## 既知の問題と解決済み修正

| 問題 | 原因 | 修正 |
|------|------|------|
| 全検索 400 エラー | `private` BOOL payload index 未設定 | Qdrant で手動 index 作成 |
| 給与明細が見つからない | LLM がツール使わず直接回答 | システムプロンプトに英語+日本語の強制ルール追加 |
| metadata_search 3回失敗 | LLM が must+should 両方出力 | `_fix_company_must_should_duplication()` 追加 |
| GoogleGenAI API キー未設定 | 4ファイルで GoogleGenAI 依存 | 全て `Settings.llm` (OpenAI) に変更 |
| 契約書名が「（テキスト抽出なし）」 | OCR プレースホルダーが有効値を上書き | `ORDER BY updated_at ASC` + プレースホルダー無視ロジック |

## 重要なファイルパス

```
app/api/internal/contract_ingest.py          # Webhook でのインジェスト
app/services/chatbot/tools/metadata_search/
  text_to_qdrant_filters.py                  # Qdrant フィルタ変換（_fix_company_must_should_duplication含む）
  query_metadata_extractor.py                # クエリ解析（Settings.llm使用）
app/services/chatbot/prompts/
  system_prompts_jp_v3.py                    # システムプロンプト（MANDATORY RULE含む）
scripts/recreate_collection.py              # コレクション再作成（payload index 設定含む）
```

## Docker コマンド

```bash
# コンテナ再起動（イメージ再ビルド込み）
docker build -t conpass-agent . && docker rm -f conpass-agent && docker run -d \
  --name conpass-agent --env-file .env \
  -p 8000:8080 --network conpass-backend_default conpass-agent

# ログ確認
docker logs conpass-agent --tail=50

# コンテナ内でスクリプト実行
docker exec conpass-agent bash -c 'cd /app && /app/.venv/bin/python -m scripts.XXX'
```

## Qdrant 注意点

- 日付は ISO 文字列で保存 (`'2025-04-01'` 型 `str`)
- 会社名検索は `should` (OR) を使う — `must` では全フィールド同時マッチが必要で実質不可能
- `private` BOOL フィールドの payload index が必須

## ユーザー設定

- 日本語で回答する
- コミットメッセージも日本語
- 過剰実装しない、最小限の変更のみ
