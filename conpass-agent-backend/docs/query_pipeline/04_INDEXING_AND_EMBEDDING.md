# ConPass AI Assistant — Indexing and Embedding

This document describes the current design and implementation of embedding generation, vector storage, and index management.

## Embedding Model

| Attribute | Value |
|-----------|-------|
| **Model** | OpenAI; configurable via `EMBEDDING_MODEL` (e.g. `text-embedding-3-small`, `text-embedding-3-large`) |
| **Configuration** | `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `OPENAI_API_KEY` |
| **Dimensionality** | Configurable via `EMBEDDING_DIM` (e.g. 1536 for text-embedding-3-small, 1024 for text-embedding-3-large). deploy.sh uses text-embedding-3-large with 1024. |
| **Usage** | Dense vector for semantic similarity |

```python
# cloud/cloud_run/generate_embeddings/model.py
_embedding_model = OpenAIEmbedding(
    model=embedding_pipeline_config.EMBEDDING_MODEL,
    dimensions=embedding_pipeline_config.EMBEDDING_DIM,
    api_key=embedding_pipeline_config.OPENAI_API_KEY,
)
```

## Scope of Vectorization

| Scope | Included |
|-------|----------|
| **Body text** | Yes — chunk text is embedded |
| **Title** | No — not concatenated with body for embedding |
| **Metadata** | No — metadata is stored in payload only, not used for embedding |
| **Concatenated metadata** | No |

Only the chunk text is passed to the embedding model. Metadata is attached to the Qdrant payload for filtering and display.

## Vector DB, Distance Function, and Indexing

| Attribute | Value |
|-----------|-------|
| **Vector DB** | Qdrant |
| **Collection** | Single collection per environment (`QDRANT_COLLECTION`) |
| **Named vectors** | `dense` (OpenAI), `sparse` (BM25) |
| **Dense distance** | Cosine similarity (Qdrant default for dense) |
| **Sparse** | BM25-style (FastEmbed Qdrant/bm25) |
| **Index type** | HNSW (Qdrant default) |

The collection must be created with named vectors `dense` and `sparse` to support hybrid search.

## Sparse Embedding (BM25)

| Attribute | Value |
|-----------|-------|
| **Model** | FastEmbed `Qdrant/bm25` |
| **Purpose** | Keyword-style matching; combined with dense via RRF fusion |
| **Consistency** | Same model used in ingestion and query |

## Payload Indexes

Payload indexes are created for metadata filtering:

| Field | Schema Type |
|-------|-------------|
| name | KEYWORD |
| directory_id | INTEGER |
| contract_id | INTEGER |
| private | BOOL |
| 契約書名_title | KEYWORD |
| 会社名_甲_company_a | KEYWORD |
| 会社名_乙_company_b | KEYWORD |
| 会社名_丙_company_c | KEYWORD |
| 会社名_丁_company_d | KEYWORD |
| 契約種別_contract_type | KEYWORD |
| 裁判所_court | KEYWORD |
| 契約日_contract_date | DATETIME |
| 契約開始日_contract_start_date | DATETIME |
| 契約終了日_contract_end_date | DATETIME |
| 契約終了日_cancel_notice_date | DATETIME |
| 自動更新の有無_auto_update | BOOL |

Indexes are ensured at startup via `ensure_payload_indexes()`.

## Index Update Strategy

| Scenario | Action |
|----------|--------|
| **New contract** | Process (chunk, embed, store); store metadata + hash in Redis |
| **Unchanged** (hash matches) | Skip processing |
| **Updated** (hash differs) | Delete Qdrant points by `contract_id`; reprocess; update Redis |
| **Deleted** | Pub/Sub `event_type: "deleted"`; delete from Qdrant and Redis |

No full re-indexing by default. Incremental updates are driven by:

- **Batch ingestion**: CF1 fetches from MySQL, publishes to Pub/Sub
- **Contract Sync Handler**: Webhook on contract create/update; publishes to same Pub/Sub topic

## Key Files

- [cloud/cloud_run/generate_embeddings/model.py](../../cloud/cloud_run/generate_embeddings/model.py) — Dense embedding model
- [cloud/cloud_run/generate_embeddings/vector_db.py](../../cloud/cloud_run/generate_embeddings/vector_db.py) — Qdrant storage, dense + sparse vectors
- [cloud/cloud_run/generate_embeddings/qdrant_indexes.py](../../cloud/cloud_run/generate_embeddings/qdrant_indexes.py) — Payload index definitions
- [cloud/cloud_run/generate_embeddings/sparse_model.py](../../cloud/cloud_run/generate_embeddings/sparse_model.py) — Sparse (BM25) embedding
