# ConPass AI Assistant — Query Pipeline Documentation

This directory contains fact-based documentation of the ConPass AI Assistant Query Pipeline, from RAG retrieval to answer generation. The purpose is to accurately describe the current design and implementation (not to evaluate whether it is good or bad).

## Document Index

| # | Document | Description |
|---|----------|--------------|
| 1 | [01_OVERALL_ARCHITECTURE.md](01_OVERALL_ARCHITECTURE.md) | System architecture, processing flow, main components, execution mode |
| 2 | [02_INGESTION_ASSUMPTIONS.md](02_INGESTION_ASSUMPTIONS.md) | OCR/text extraction, normalization, version management, linking |
| 3 | [03_CHUNKING_DESIGN.md](03_CHUNKING_DESIGN.md) | Chunk unit, size, overlap, metadata, tables/appendices |
| 4 | [04_INDEXING_AND_EMBEDDING.md](04_INDEXING_AND_EMBEDDING.md) | Embedding model, vector DB, indexing, update strategy |
| 5 | [05_RETRIEVAL_DESIGN.md](05_RETRIEVAL_DESIGN.md) | Hybrid search, topK, filters, scope control |
| 6 | [06_RERANKING_AND_SCORING.md](06_RERANKING_AND_SCORING.md) | Reranking (none), scoring, deduplication |
| 7 | [07_ANSWER_GENERATION.md](07_ANSWER_GENERATION.md) | Prompt structure, tool routing, citation, conversation history |
| 8 | [08_EVALUATION_LOGGING_KNOWN_ISSUES.md](08_EVALUATION_LOGGING_KNOWN_ISSUES.md) | Evaluation, logging, referenced chunks, known issues |

## Quick Overview

- **Query Pipeline**: Real-time agent-based flow; user message → tool selection (semantic_search, metadata_search, read_contracts, get_file_content, document_diffing, csv_generation, plus risk_analysis, web_search) → LLM answer → streamed response
- **Ingestion Pipeline**: Batch via Pub/Sub; MySQL → Cloud Run → Qdrant + Redis
- **Retrieval**: Hybrid (dense + sparse) with RRF fusion; no reranker
- **Embedding**: OpenAI (dense) + FastEmbed Qdrant/bm25 (sparse)
- **Vector DB**: Qdrant with named vectors
- **OCR**: Used for File Upload (PDFs/images) and standalone OCR API; not used by Risk Analysis or main ingestion
