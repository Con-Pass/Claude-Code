# Qdrant ペイロード `chunk_index` / `total_chunks` の解説

## 生成ロジック

`contract_ingest.py` の処理フローです：

```
契約書テキスト全文（例: 3,000文字）
  ↓  _chunk_text()
  ├─ chunk[0]: 0〜1024文字          chunk_index=0, total_chunks=3
  ├─ chunk[1]: 924〜1948文字        chunk_index=1, total_chunks=3
  └─ chunk[2]: 1848〜2872文字       chunk_index=2, total_chunks=3
                ↑ 「nditions of the...」はここ
```

**定数**（デフォルト値）
- `_CHUNK_SIZE = 1024` 文字
- `_CHUNK_OVERLAP = 100` 文字（前後のチャンクと100文字重複させる）

つまり「nditions of the Original Agreement remain in full…」は、**テキストを固定長1024文字で切り出した際に文の途中から始まったチャンク**です。文頭の「co**nditions**」は前のチャンク（chunk_index=1）の末尾100文字に含まれています。

---

## ペイロードに記録することの意味

| フィールド | 目的 |
|---|---|
| `chunk_index` | **ポイントIDの決定論的生成**: `uuid5(NAMESPACE_DNS, "{contract_id}_{i}")` でチャンクごとにユニークIDを確定する。再インデックス時も同じIDが生成されるため、`upsert` で冪等に上書きできる |
| `total_chunks` | **境界の把握**: このチャンクが契約書の最後（`chunk_index == total_chunks - 1`）か中間かを判定できる。先頭・末尾チャンクの取得や、前後チャンクのフェッチに活用できる |
| 両方 | **デバッグ・監視**: Qdrant 管理画面で「この契約書は全部で3チャンクのうちの3番目」と人間が一目で把握できる |

---

## 現状の使われ方

現在のコードでは `chunk_index` / `total_chunks` はペイロードに保存されるだけで、**検索クエリの絞り込み条件としては使用されていません**。

実際の検索では `contract_id` と `directory_id` でフィルタリングし、セマンティック類似度の高いチャンクを返しています。`chunk_index` / `total_chunks` は将来的に「ヒットしたチャンクの前後を取得して文脈を補完する」用途や、デバッグのためのメタデータとして設計されています。
