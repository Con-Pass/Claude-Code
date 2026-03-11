# ConPass AI Assistant — Ingestion-Side Assumptions

This document describes the current design and implementation of the ingestion pipeline, including OCR/text extraction, normalization, and version management.

## OCR and Text Extraction

### Main Contract Ingestion (No OCR)

The main ingestion pipeline does **not** use OCR. Contract body text comes from:

- **Source**: MySQL `conpass_contractbody` table
- **Format**: HTML, URL-encoded (e.g. `%3Cp%3E...%3C%2Fp%3E`)
- **Selection**: Only the latest version per contract (`MAX(version)` subquery)

Processing steps:

1. Base64 decode Pub/Sub message
2. URL-decode body: `urllib.parse.unquote(body_raw)`
3. HTML to plain text: `BeautifulSoup(decoded, "html.parser").get_text(strip=True)`

### OCR (File Upload and Standalone API)

OCR is **not** used by the Risk Analysis Tool. Risk Analysis fetches contract text from ConPass API via `get_document_from_docstore` (same as read_contracts_tool); contracts are already digital text.

OCR is used in:

- **File Upload Service**: When users upload PDF or image files, Google Document AI extracts text for chat context (e.g. document diffing, CSV generation). Tesseract is available but File Upload uses Document AI.
- **Standalone OCR API** (`/api/v1/ocr/extract`, `/extract-structured`): Direct endpoints for text extraction from PDFs/images; Tesseract or Document AI selectable.

OCR is **not** part of the main contract ingestion path.

## Input Patterns Prone to Accuracy Degradation

| Pattern | Behavior |
|---------|----------|
| **Empty body** | Contract skipped; warning logged |
| **Missing directory** | Contract skipped; warning logged |
| **Invalid/malformed HTML** | BeautifulSoup may produce incomplete or noisy text |
| **URL-encoding issues** | `unquote` may fail or produce wrong characters if encoding is non-standard |
| **Very long text** | Chunked; no special handling for structure |
| **Tables in HTML** | Rendered as plain text; structure not preserved |
| **Multi-column layout** | Flattened to single text stream |

## Normalization Processing

| Aspect | Implementation |
|--------|----------------|
| **Line breaks** | Preserved in raw text; chunker uses `\n` as sentence boundary |
| **Multi-column layouts** | Not detected; treated as continuous text |
| **Tables** | HTML stripped; content as plain text, no structure |
| **Headers/footers** | Not identified or removed |
| **Full-width/half-width** | No explicit normalization; `\u3000` (ideographic space) replaced with ` ` in chunker |
| **Punctuation** | Japanese + Western punctuation (。．.!！?？) used as sentence boundaries in chunker |

Relevant code in chunker:

```python
# cloud/cloud_run/generate_embeddings/chunker.py
text = text.replace("\u3000", " ").strip()
SENTENCE_BOUNDARY_RE = re.compile(r"[。．.!！?？\n]")
```

## Article Numbers, Headings, and Hierarchical Structure

**Not extracted or preserved.** The system:

- Does not parse article numbers (e.g. 第1条, Article 1)
- Does not extract or preserve headings
- Does not maintain hierarchical structure (sections, clauses, sub-clauses)
- Chunks by fixed length with overlap; semantic boundaries are approximate (sentence endings)

## Version Management and Linking

### Contract Body Versions

- **Source**: `conpass_contractbody` has a `version` column
- **Ingestion**: Fetches only the latest version per contract (via `MAX(version)` in upstream fetcher)
- **Amendments**: Not explicitly linked; if an amendment updates the body, it is stored as a new version and ingestion will pick it up on next sync

### Hash-Based Deduplication

- **Hash**: SHA256 of `{"text": text, "metadata": metadata}` (sorted keys)
- **Redis**: Stores `{metadata, hash}` per `contract_id` (text not stored; fetched from ConPass API when needed)
- **Logic**:
  - New contract: process, store in Qdrant + Redis
  - Unchanged (hash matches): skip
  - Changed (hash differs): delete old Qdrant points by `contract_id`, reprocess, update Redis

### Linking

- **Contract ID**: Links to ConPass frontend URL: `{CONPASS_FRONTEND_BASE_URL}/contract/{contract_id}`
- **Amendments / memorandums**: No explicit linking in the ingestion or vector store; relationship would exist only in the source ConPass backend schema

## Key Files

- [cloud/cloud_run/generate_embeddings/doc_generator.py](../../cloud/cloud_run/generate_embeddings/doc_generator.py) — Pub/Sub parsing, HTML extraction, metadata mapping
- [cloud/cloud_run/generate_embeddings/chunker.py](../../cloud/cloud_run/generate_embeddings/chunker.py) — Text chunking with Japanese boundaries
- [cloud/cloud_run/generate_embeddings/pipeline.py](../../cloud/cloud_run/generate_embeddings/pipeline.py) — Hash check, Redis, Qdrant update logic
- [docs/INGESTION_PIPELINE_ARCHITECTURE.md](../INGESTION_PIPELINE_ARCHITECTURE.md) — Full ingestion architecture
