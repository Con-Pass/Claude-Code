# ConPass AI Assistant — Retrieval Design

This document describes the current design and implementation of the retrieval layer used by the ConPass AI Assistant.

## Retrieval Approach

| Aspect | Implementation |
|--------|----------------|
| **Primary** | Hybrid search (dense + sparse) |
| **Fusion** | RRF (Reciprocal Rank Fusion) via Qdrant Universal Query API |
| **Fallback** | Dense-only search if hybrid fails |
| **Query expansion** | None — agent may rephrase per system prompt, but no automatic expansion |

### Dense Search

- Query is embedded with the same OpenAI model used at ingestion
- Cosine similarity over the `dense` named vector

### Sparse Search

- Query is embedded with FastEmbed `Qdrant/bm25` (same as ingestion)
- BM25-style scoring over the `sparse` named vector

### Hybrid Fusion

- Prefetch: `limit = top_k * 2` for both dense and sparse
- Fusion: `models.FusionQuery(fusion=models.Fusion.RRF)`
- Final `limit = top_k` after fusion

## topK Configuration

| Parameter | Default | Configurable Via | Notes |
|-----------|---------|------------------|-------|
| **TOP_K** | 100 | `settings.TOP_K` | Number of results returned from Qdrant (before deduplication) |
| **Prefetch limit** | `top_k * 2` | Hardcoded | Fetched per vector type for RRF fusion |

## Metadata Fields Used as Filters

| Field | Usage |
|-------|-------|
| **directory_id** | Must match user's allowed directories (from ConPass API) |
| **private** | Must not be True (excludes private nodes) |

Filter construction:

```python
# app/services/chatbot/tools/semantic_search/semantic_search_tool.py
must.append({"key": "directory_id", "match": {"value": dir_id}})
# or match any of multiple directory_ids
must.append({"key": "directory_id", "match": {"any": directory_ids}})
must_not.append({"key": "private", "match": {"value": True}})
```

## Query Normalization and Synonym Expansion

| Mechanism | Status |
|-----------|--------|
| **Query normalization** | None — raw query passed to embedding and sparse model |
| **Synonym expansion** | None |
| **Stemming / lemmatization** | None |
| **Agent rephrasing** | System prompt instructs agent to use user's query; minimal rephrasing for context |

## Scope Control for Multi-Contract Search

| Aspect | Implementation |
|--------|----------------|
| **Scope** | `directory_ids` from ConPass API (`get_allowed_directories`) |
| **Filter** | All semantic/metadata searches filter by `directory_id IN allowed_directory_ids` |
| **User isolation** | JWT identifies user; ConPass API returns only directories the user can access |

## Semantic Search vs Metadata Search

| Tool | Purpose | Backend |
|------|---------|---------|
| **semantic_search** | Content-based discovery across contracts | Qdrant hybrid search (dense + sparse) |
| **metadata_search** | Filter/list contracts by metadata (company, dates, type, etc.) | Qdrant scroll with filter (to get matching contract IDs); Redis `get_metadata_from_docstore` (to fetch metadata for display) |

The agent selects the tool based on user intent (see system prompt and tool descriptions).

## Key Files

- [app/services/chatbot/tools/semantic_search/semantic_search_tool.py](../../app/services/chatbot/tools/semantic_search/semantic_search_tool.py) — Hybrid search, filter building
- [app/services/chatbot/tools/metadata_search/metadata_search_tool.py](../../app/services/chatbot/tools/metadata_search/metadata_search_tool.py) — Metadata filtering, scroll
