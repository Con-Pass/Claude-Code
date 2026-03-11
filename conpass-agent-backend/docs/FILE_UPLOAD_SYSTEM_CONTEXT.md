# File Upload System Refactor - Technical Implementation Context

## 1. Executive Summary
This document outlines the architectural changes required to refactor the **File Upload Service** and **Upload API** to move away from local file storage and direct vector indexing towards a cloud-native, token-aware pipeline using **Google Cloud Storage (GCS)** and **Tiktoken**.

## 2. Current Implementation Analysis
The existing system relies on:
- **Service**: `app/services/file_upload_service.py`
- **Storage**: Local filesystem (`output/uploaded`).
- **Processing**: Direct ingestion into `LlamaIndex` vector store (`VectorStoreIndex` with `IngestionPipeline`).
- **Endpoint**: `app/api/v1/upload.py` (accepts Base64 encoded content).

**Limitations**:
- Stateful storage (local disk), posing scalability issues.
- Tight coupling with vector indexing during upload.
- No pre-validation of token usage (cost/context window risks).

## 3. New System Design

### 3.1. Worklow Overview
The new pipeline decouples storage from indexing and introduces strict token usage validation using Tiktoken.

**Sequence**:
1.  **Client Upload**: User uploads file (Frontend -> API).
2.  **File Processing**: API detects file type and extracts raw text locally.
3.  **Token Validation**:
    -   Calculate token count for the extracted text using `tiktoken`.
    -   **Condition**: If `token_count > MAX_TOKEN_LIMIT`, abort and throw `400 Bad Request`.
4.  **Cloud Storage**:
    -   Upload **original file** to GCS bucket.
    -   Upload **extracted text** (as `.txt`) to GCS bucket (same path/prefix).
5.  **Response**: Return Cloud CDN URLs for both the file and the extracted text.

### 3.2. Detailed Implementation Specifications

#### A. API Endpoint (`app/api/v1/upload.py`)
-   **Method**: `POST /v1/upload` (Recommend renaming/verifying route).
-   **Content-Type**: `multipart/form-data` (Recommended for efficiency) or `application/json` (Base64 - preserving current interface if required, but Multipart is preferred for large files).
-   **Input**: File binary/blob.

#### B. Text Extraction & Type Detection
-   **Service**: `app.services.ocr_service.OCRService`.
-   **Strategy**:
    -   **PDFs & Images**: Use `OCRService.extract_text_from_file` with `engine="document_ai"` (delegates to `GoogleDocumentAIService`).
    -   **CSV/Excel**: Use appropriate Python tools (e.g., `pandas`, `csv` module).
    -   **Word (DOCX)**: Use `docx2txt` or similar extraction library.
    -   **Text (TXT)**: Read directly.
-   **File Type Detection**: Continue using `python-magic` (already used in `GoogleDocumentAIService`) or `mimetypes` to route to the correct extractor.

#### C. Token Counting
-   **Library**: `tiktoken` (Use `uv add tiktoken` to install).
-   **Logic**:
    ```python
    import tiktoken
    encoder = tiktoken.get_encoding("cl100k_base")
    count = len(encoder.encode(extracted_text))
    if count > settings.UPLOAD_MAX_TOKENS:
        raise HTTPException(...)
    ```

#### D. Google Cloud Storage & Cloud CDN
-   **Library**: `google-cloud-storage`.
-   **Structure**:
    -   Original File: `gs://{BUCKET_NAME}/files/{UUID}/{filename.ext}`
    -   Extracted Text: `gs://{BUCKET_NAME}/extracted/{UUID}.txt`
-   **Serving**:
    -   Construct URL using CDN Domain: `https://{CDN_DOMAIN}/files/{UUID}/{filename.ext}`.

#### E. Infrastructure Setup
For detailed instructions on configuring GCS and the CDN, please refer to the [GCS & CDN Setup Guide](./GCS_CLOUDFRONT_SETUP_GUIDE.md).

### 3.3. Configuration Requirements (`app/core/config.py`)
New environment variables required:
-   `GCS_BUCKET_NAME`: Target Google Cloud Storage bucket.
-   `CDN_DOMAIN`: Domain for serving files (e.g., `cdn.example.com`).
-   `UPLOAD_MAX_TOKENS`: Integer threshold for rejection (e.g., `32000`).
-   `TIKTOKEN_ENCODING`: Default to `cl100k_base`.

## 4. Migration Steps
1.  **Dependencies**: Add `google-cloud-storage` and `tiktoken` using `uv` (e.g., `uv add google-cloud-storage tiktoken`).
2.  **Service Refactor**: Rewrite `FileUploadService` to remove local disk write and vector logic. Implement `upload_to_gcs` and `validate_tokens`.
3.  **API Update**: Update controller to handle the new service response and error states.
4.  **Infrastructure**: Ensure GCS bucket exists and is public-readable (or signed URLs used) and Cloud CDN is configured.

## 5. Proposed API Response
```json
{
  "id": "uuid-string",
  "name": "filename.pdf",
  "file_url": "https://cdn.example.com/uuid/filename.pdf",
  "text_url": "https://cdn.example.com/uuid/filename.txt",
  "token_count": 1450,
  "size_bytes": 102400
}
```
