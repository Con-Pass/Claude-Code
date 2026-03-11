# [PoC] RAG Pipeline Improvements for MS1

## Summary

This branch (`poc/rag-pipeline-tuning`) contains proof-of-concept implementations for the RAG pipeline improvements planned for MS1 (Milestone 1: Value Creation from Existing Data). The goal is to validate new knowledge sources, retrieval quality enhancements, and evaluation infrastructure before integrating into the main development pipeline.

**All new features are behind feature flags and disabled by default.** No existing functionality is affected.

## Changes

### ④ Law & Compliance
- **Law search tool** (`law_search/`): Cross-search between laws and contracts using Qdrant hybrid search with checkpoint-based evaluation and `absence_is_risk` scoring
- **Law ingestion** (`law_ingest.py`): Internal API endpoint to ingest law text chunks into the `conpass_laws` Qdrant collection
- **e-Gov crawler** (`egov_law_fetcher/`): Cloud Run service to fetch laws from the e-Gov API, with change detection and XML parsing. Includes Cloud Scheduler config
- **Embedding pipeline** (`generate_embeddings/`): Added `contract_classifier.py` for law/contract type classification and `pipeline_metrics.py` for ingestion monitoring. Updated `main.py` to detect `source_type=law_regulation` from Pub/Sub attributes
- **Compliance scoring** (`compliance_score_service.py`, `compliance_tool.py`): Agent tool and service for compliance evaluation based on law collection search results
- **Local ingestion script** (`scripts/local_law_ingest.py`): For local development and testing

### ① Playbook / Templates
- **Template service** (`template_service.py`): Template engine (344 lines) with `contract_templates` Qdrant collection, pre-loaded with construction/lease/NDA/SLA defaults
- **Template compare tool** (`template_compare_tool.py`): Agent tool for listing and comparing templates against contracts
- **Template API** (`api/v1/template.py`): REST endpoint for template CRUD

### ③ Feedback
- **Feedback endpoint** (`api/v1/feedback.py`): `POST /v1/feedback` with rating, comment, tool_used, and result_contract_ids
- **Feedback schema** (`schemas/feedback.py`): Request/Response models with Firestore persistence

### ⑥ Reranker & Search Cache
- **Cohere reranker** (`reranker.py`): Async integration with `rerank-multilingual-v3.0`, configurable score threshold filtering. **Default: OFF** (`RERANKER_ENABLED=false`)
- **Search cache** (`search_cache.py`): In-memory TTL cache (search: 5min, embedding: 1hr). **Default: OFF**

### Cross-cutting
- **Feature flags** (`feature_flags.py`): Firestore + env-backed toggle system for `use_reranker`, `query_expansion`, `search_cache`, `multi_agent_enabled`, etc.
- **Config** (`config.py`): Added `QDRANT_LAWS_COLLECTION`, `EMBEDDING_PROVIDER`, `MULTI_AGENT_ENABLED`, Langfuse settings (+21 lines)
- **Router** (`router.py`): Registered law_internal, feedback, template, compliance routers. Excluded: benchmark, contract_ingest, legal_commands
- **Tools** (`tools.py`): Registered `law_search_tool` and `template_compare_tool` in both `get_all_tools` and `get_assistant_tools`. Excluded: benchmark tools
- **Semantic search** (`semantic_search_tool.py`): RRF parameters via environment variables, reranker integration, added `_search_law_regulations` method (+424 lines)
- **System prompts**: Added `system_prompts_en_v6.py`, switched CDI agent to `system_prompts_jp_v5`
- **Engine** (`engine.py`): Multi-agent decision via feature flag (+20 lines)
- **Dependencies** (`pyproject.toml`): Added `cohere`, `langdetect`, and other PoC dependencies (+169 lines)

### Evaluation
- **Evaluation runner** (`evaluation_runner.py`): Framework for offline RAG quality assessment
- **Metrics** (`metrics.py`): MRR, Precision@K, Recall@K calculation
- **Test queries** (`test_queries.yaml`): Curated evaluation query set
- **Test suite** (`test_evaluation.py`, `conftest.py`): pytest integration

## Discussion Points

The following items require discussion with the development team before merging:

1. **Law management UI placement**: Currently the law CRUD API is under `setting/law/*` (admin-side). Should we also expose a read-only law search interface on the user-facing side? Or keep it admin-only with the AI agent as the user-facing access point?

2. **Playbook UI placement**: Template registration and editing should remain admin-side. Should template browsing and comparison be exposed on the user-facing side? Possible split:
   - User side: Browse templates, compare against own contracts
   - Admin side: Register, edit, delete templates, set default templates per contract type

3. **Reranker / Query expansion**: Both are **default OFF** via feature flags. The development team can enable and test independently. Query expansion (synonym dictionary) is not included in this PR yet — planned for a follow-up commit.

4. **System prompt versioning**: This PR introduces `v5` (Japanese) and `v6` (English). The CDI agent currently uses v5. Need to align on prompt version management strategy going forward.

5. **Pub/Sub integration for law ingestion**: The e-Gov crawler → Pub/Sub → embedding pipeline path is implemented but not tested against the production Pub/Sub topic. Manual ingestion via `local_law_ingest.py` or the internal API works independently.

## Not Included (Planned for Follow-up Commits)

| Item | Reason | Status |
|------|--------|--------|
| ② Contract relations (`contract_ingest.py`) | Graph index design not finalized | PoC development ongoing |
| ⑤ Synonym dictionary (`query_expander.py`) | Dictionary coverage expansion and LLM query rewrite pending | PoC development ongoing |

## How to Test

### Prerequisites
- Qdrant instance with `conpass_laws` and `contract_templates` collections
- Firestore access for feature flags and feedback storage
- Cohere API key (for reranker, optional)

### Environment Variables
```bash
# Required for law features
QDRANT_LAWS_COLLECTION=conpass_laws

# Optional — all default to OFF
RERANKER_ENABLED=false
SEARCH_CACHE_ENABLED=false
MULTI_AGENT_ENABLED=false
```

### Feature Flag Overrides
Feature flags can be toggled via:
1. Firestore document (`feature_flags` collection)
2. Environment variables (take precedence)

### Quick Validation
```bash
# 1. Run evaluation suite
cd evaluation/
pytest test_evaluation.py -v

# 2. Test law ingestion locally
python scripts/local_law_ingest.py --file /path/to/law.txt

# 3. Verify feature flags
curl -X GET http://localhost:8080/internal/feature-flags
```
