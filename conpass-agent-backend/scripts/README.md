# Scripts

This directory contains utility scripts for the ConPass Agent backend.

## Available Scripts

### `ocr_implementation_script.py`

Test script to verify OCR service implementation without starting the full server.

**Usage:**

```bash
uv run python scripts/test_ocr_implementation.py
```

**What it tests:**

- Tesseract installation and configuration
- Japanese language pack availability
- OCR text extraction from test images (bytes)
- OCR text extraction with BytesIO objects
- Basic OCR service functionality

**Output:**

- Clean, professional text output
- Clear PASS/FAIL status indicators
- Detailed test results and troubleshooting information

**Requirements:**

- Tesseract OCR installed
- Japanese language pack (`tesseract-ocr-jpn`)
- Python dependencies installed (`uv sync`)

### `ocr_api_script.py`

Test script to verify OCR API endpoints (health and extract) using HTTP requests.

**Usage:**

```bash
uv run python scripts/test_ocr_api.py
```

**What it tests:**

- OCR health endpoint (`GET /api/v1/ocr/health`)
- OCR extract endpoint (`POST /api/v1/ocr/extract`)
- API response validation
- Error handling

**Requirements:**

- FastAPI server running on port 8001
- OCR service properly configured
- Python dependencies installed (`uv sync`)

**Note:** Make sure the server is running before executing this script:

```bash
uv run fastapi dev --port 8001
```

### `ocr_benchmark.py`

Japanese OCR benchmark system for accuracy testing and performance evaluation.

**Usage:**

```bash
uv run python scripts/ocr_benchmark.py
```

**What it tests:**

- Japanese text recognition accuracy (hiragana, katakana, kanji, mixed)
- Confidence scoring for Japanese OCR
- Quality grading system (A-F scale)
- Performance metrics and processing times
- Character Error Rate (CER) calculations

**Features:**

- **Test Case Generation**: Creates test images with known Japanese text
- **Accuracy Benchmarking**: Compares extracted text with expected results
- **Script-Specific Analysis**: Separate accuracy for hiragana, katakana, and kanji
- **Quality Assessment**: Grades OCR results based on accuracy and confidence
- **Performance Metrics**: Tracks processing time and resource usage

**Requirements:**

- Tesseract OCR with Japanese language pack
- Python dependencies installed (`uv sync`)
- Japanese fonts available on system

**Output Example:**

```text
Japanese OCR Benchmark Results:
==================================================
Test 1: hiragana - Accuracy: 100.0%, Confidence: 30.4%, Grade: F
Test 2: katakana - Accuracy: 100.0%, Confidence: 28.3%, Grade: F
Test 3: kanji - Accuracy: 100.0%, Confidence: 34.1%, Grade: F
Test 4: mixed - Accuracy: 84.8%, Confidence: 29.4%, Grade: F

Overall Metrics:
- Average Accuracy: 96.2%
- Average Confidence: 30.6%
- Passed Tests: 0/4
```

### `test_document_ai_performance.py`

Performance test script for Google Document AI optimization.

**Usage:**

```bash
uv run python scripts/test_document_ai_performance.py
```

**What it tests:**

- Document AI processing performance with optimizations
- Parallel structured data extraction
- Thread-safe client initialization
- Performance metrics and processing times

**Features:**

- **Performance Testing**: Measures processing time improvements
- **Optimization Validation**: Tests parallel extraction features
- **Configuration Testing**: Validates optimization settings
- **Structured Content**: Creates test documents with entities, tables, and form fields

**Requirements:**

- Python dependencies installed (`uv sync`)
- Google Cloud Document AI configured (optional for testing)

**Output Example:**

```text
Document AI Performance Test
==================================================
1. Creating test document...
   PASS: Test document created (45678 bytes)

2. Testing with optimizations enabled...
   PASS: Document AI processing completed in 8.5s
   Text length: 1250 characters
   Entities: 5
   Tables: 2
   Form fields: 3
   Confidence: 0.92

SUCCESS: Document AI performance optimizations are working!
```

## Running Scripts

All scripts should be run from the project root directory using `uv run`:

```bash
# From project root
uv run python scripts/script_name.py
```
