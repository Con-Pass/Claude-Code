# ConPass AI Assistant — Chunking Design

This document describes the current design and implementation of the chunking strategy used in the ingestion pipeline.

## Chunk Splitting Unit

- **Type**: Fixed-length with overlap
- **Boundary awareness**: Japanese and Western sentence boundaries (。．.!！?？\n) are preferred when available
- **Fallback**: If no boundary exists in the overlap window, chunk ends at `chunk_size` characters

## Chunk Size, Overlap, and Maximum Length

| Parameter | Configurable Via | Notes |
|-----------|------------------|-------|
| **CHUNK_SIZE** | `embedding_pipeline_config.CHUNK_SIZE` (ingestion), `settings.CHUNK_SIZE` (app) | Maximum characters per chunk. Ingestion: no default (env required); deploy.sh uses 1000 for dev/staging/prod. App config default: 1024. |
| **CHUNK_OVERLAP** | `embedding_pipeline_config.CHUNK_OVERLAP` (ingestion), `settings.CHUNK_OVERLAP` (app) | Overlap between consecutive chunks. Ingestion: no default (env required); deploy.sh uses 100. App config default: 100. |
| **Maximum length** | — | No explicit cap; long documents produce many chunks |

## Boundary Logic

```python
# cloud/cloud_run/generate_embeddings/chunker.py
SENTENCE_BOUNDARY_RE = re.compile(r"[。．.!！?？\n]")

# For each chunk:
# 1. Take text from start to min(start + chunk_size, text_length)
# 2. If end < text_length and chunk_overlap > 0:
#    - Search for boundaries in the last chunk_overlap characters
#    - Use the LAST boundary found to shorten the chunk end
# 3. next_start = end - chunk_overlap (ensuring progress)
```

The chunker prefers to end at a sentence boundary within the overlap window to avoid mid-sentence cuts.

## Metadata Attached to Each Chunk

Every chunk inherits the document metadata. Stored fields include:

| Field | Source | Description |
|-------|--------|-------------|
| **contract_id** | Contract | Unique contract identifier |
| **name** | Contract | Contract name |
| **directory_id** | Directory | Directory for scope filtering |
| **契約書名_title** | Metadata | Contract title |
| **会社名_甲_company_a** | Metadata | Party A company name |
| **会社名_乙_company_b** | Metadata | Party B company name |
| **会社名_丙_company_c** | Metadata | Party C company name |
| **会社名_丁_company_d** | Metadata | Party D company name |
| **契約種別_contract_type** | Metadata | Contract type |
| **裁判所_court** | Metadata | Court jurisdiction |
| **契約日_contract_date** | Metadata | Contract date (YYYY-MM-DD) |
| **契約開始日_contract_start_date** | Metadata | Start date |
| **契約終了日_contract_end_date** | Metadata | End date |
| **契約終了日_cancel_notice_date** | Metadata | Cancel notice date |
| **自動更新の有無_auto_update** | Metadata | Auto-renewal (bool) |
| **private** | Pipeline | Set to False for all ingested docs |
| **node_id** | Pipeline | Unique node ID (UUID) |
| **text** | Chunk | Chunk text content |

## Handling of Tables and Appendices

| Content Type | Handling |
|--------------|----------|
| **Tables** | Treated as plain text; HTML structure stripped by BeautifulSoup |
| **Appendices** | Same as body; no separate chunking or tagging |
| **Image-based content** | Not processed in main ingestion; OCR used in File Upload for user-uploaded PDFs/images |

There is no:

- Separate chunk type for tables
- Serialization of table structure (rows/columns)
- Image-based handling in the ingestion pipeline

## Key Files

- [cloud/cloud_run/generate_embeddings/chunker.py](../../cloud/cloud_run/generate_embeddings/chunker.py) — Chunking implementation
- [cloud/cloud_run/generate_embeddings/pipeline.py](../../cloud/cloud_run/generate_embeddings/pipeline.py) — Calls chunker, attaches metadata
- [cloud/cloud_run/generate_embeddings/metadata_map.py](../../cloud/cloud_run/generate_embeddings/metadata_map.py) — Metadata key mapping from ConPass schema
