# ConPass AI Assistant — Evaluation, Logging, and Known Issues

This document describes the current state of evaluation, logging, feedback collection, and known limitations.

## Offline Evaluation

| Aspect | Status |
|--------|--------|
| **Evaluation framework** | None — no dedicated offline evaluation pipeline in the codebase |
| **Metrics** | No standard metrics (e.g. precision, recall, MRR, faithfulness) implemented |
| **Benchmark datasets** | None |
| **Regression testing** | Unit tests exist for components (e.g. OCR, schemas, endpoints); no RAG-specific evaluation |

## Usage Logs and Online Feedback

| Aspect | Implementation |
|--------|----------------|
| **Application logging** | Standard Python `logging`; `get_logger(__name__)` per module |
| **Log levels** | INFO, WARNING, ERROR, DEBUG |
| **Event callbacks** | `EventCallbackHandler` emits `FUNCTION_CALL`, `AGENT_STEP` for streaming compatibility |
| **Chat history** | Stored in Firestore; includes messages, annotations, user_id, chat_id |
| **Explicit feedback** | No thumbs up/down or explicit feedback collection found in codebase |

## Referenced Chunks and Scores During Answer Generation

| Aspect | Implementation |
|--------|----------------|
| **Tool outputs** | Attached to `StreamingAgentChatResponse.sources` |
| **Source nodes** | Extracted from tool outputs via `set_source_nodes()` |
| **Persistence** | Chat messages saved to Firestore; annotations may include source references |
| **Scores** | Included in semantic_search source format (`score` field); passed to agent but not separately persisted |

Tool outputs (sources with excerpt, contract_id, contract_url, score) are available during streaming and are included in the response. Whether they are stored in chat history depends on the message saver implementation.

## Known Failure Patterns and System Limitations

### From Documentation (HYBRID_SEARCH_ANALYSIS.md)

| Issue | Severity | Description |
|-------|----------|-------------|
| **Sparse model init** | Addressed | Sparse model is now initialized at startup in `model_settings.py` |
| **Score threshold on dense only** | Medium | `SCORE_THRESHOLD` applied to dense prefetch; sparse prefetch does not use it |
| **No timeout on Qdrant client** | Medium | `QDRANT_TIMEOUT_SECONDS` used in HTTP fallback but not in QdrantClient init |
| **Silent sparse failure** | Low | If sparse embedding is None, hybrid falls back to dense-only with warning log |
| **No collection verification** | Medium | Query engine does not verify collection has named vectors at startup |

### General Limitations

| Limitation | Description |
|------------|-------------|
| **No reranker** | Results from hybrid search used directly; no Cross-Encoder or reranking step |
| **No query expansion** | No synonym expansion or query reformulation |
| **No offline eval** | No systematic way to measure retrieval or answer quality |
| **OCR scope** | OCR for File Upload and standalone API; not used by Risk Analysis or main ingestion |
| **Article structure** | No extraction of article numbers, headings, or hierarchy |
| **Tables** | Rendered as plain text; structure not preserved |
| **read_contracts limit** | Max 4 contracts per call |

### Error Handling

| Scenario | Behavior |
|----------|----------|
| **Hybrid search failure** | Fallback to dense-only search |
| **Sparse model init failure** | App starts; hybrid search uses dense-only |
| **Qdrant/Redis unavailable** | Errors propagate; tool returns error structure |
| **Chat engine error** | Returns error message in `AgentChatResponse` |

## Key Files

- [docs/HYBRID_SEARCH_ANALYSIS.md](../HYBRID_SEARCH_ANALYSIS.md) — Hybrid search production readiness
- [app/services/chatbot/vercel_response.py](../../app/services/chatbot/vercel_response.py) — Streaming, source handling
- [app/services/chat_history/firestore_storage.py](../../app/services/chat_history/firestore_storage.py) — Chat persistence
- [app/core/model_settings.py](../../app/core/model_settings.py) — Sparse model init at startup
