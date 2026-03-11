# mypy: ignore-errors
import base64
from io import BytesIO
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status

from app.services.ocr_service import OCRService
from app.schemas.ocr import OCRResult, OCRHealthResponse, OCRBase64Request
from app.schemas.document_ai import DocumentAIResult
from app.core.constants import OCRConstants
from app.core.logging_config import get_logger

ocr_router = r = APIRouter()
logger = get_logger("uvicorn")


@r.post(
    "/extract",
    summary="Extract Text with OCR",
    description="Extract text from uploaded PDF or image file using Tesseract or Google Document AI",
    response_description="Extracted text and metadata",
    response_model=OCRResult,
    tags=["ocr"],
)
def extract_text(
    file: UploadFile = File(...),
    lang: str = Form(default=OCRConstants.DEFAULT_LANGUAGE),
    dpi: int = Form(default=OCRConstants.DEFAULT_DPI),
    engine: str = Form(default="tesseract"),
) -> OCRResult:
    """
    Extract text from uploaded PDF or image file using OCR.
    
    **Supported Formats:**
    - PDF (.pdf) - Scanned or image-based PDFs
    - Images (.png, .jpg, .jpeg, .tiff)
    
    **Languages:**
    - `jpn` - Japanese
    - `eng` - English  
    - `eng+jpn` - Bilingual
    
    **Parameters:**
    - `file`: Uploaded file (PDF or image)
    - `lang`: OCR language code (default: jpn)
    - `dpi`: Resolution for PDF rendering (default: 300, Tesseract only)
    - `engine`: OCR engine to use (tesseract, document_ai)
    
    **Response:**
    - `extracted_text`: Extracted text content
    - `page_count`: Number of pages processed
    - `language`: Language used for OCR
    - `file_type`: Type of file processed
    - `processing_time`: Processing time in seconds
    - `success`: Whether processing was successful
    
    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/ocr/extract" \
        -F "file=@contract.pdf" \
        -F "lang=jpn" \
        -F "dpi=300" \
        -F "engine=tesseract"
    ```
    """
    try:
        logger.info(f"Processing OCR for file: {file.filename}")

        # Validate file type
        if not file.content_type.startswith(
            (OCRConstants.SUPPORTED_PDF_TYPE, "image/")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Only PDF and image files are allowed.",
            )

        # Read file content
        file_content = file.file.read()

        # Validate engine parameter
        if engine not in ["tesseract", "document_ai"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid engine. Use 'tesseract' or 'document_ai'",
            )

        # Process with OCR service
        result = OCRService.extract_text_from_file(
            file_path=file_content, lang=lang, dpi=dpi, engine=engine
        )

        # Convert DocumentAIResult to OCRResult for consistency
        if hasattr(result, "entities"):  # DocumentAIResult
            from app.schemas.ocr import OCRResult

            return OCRResult(
                extracted_text=result.text,
                page_count=result.page_count,
                language=result.language,
                file_type=result.file_type,
                processing_time=result.processing_time,
                success=result.success,
                confidence_score=result.confidence * 100,  # Convert to 0-100 scale
                raw_confidence=result.confidence * 100,
                character_count=len(result.text),
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing OCR: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing OCR: {str(e)}",
        )


@r.post(
    "/extract-base64",
    summary="Extract Text with OCR from Base64",
    description="Extract text from base64 encoded PDF or image file using OCR",
    response_description="Extracted text and metadata",
    response_model=OCRResult,
    tags=["ocr"],
)
def extract_text_from_base64(request: OCRBase64Request) -> OCRResult:
    """
    Extract text from base64 encoded PDF or image file using OCR.

    **Supported Formats:**
    - PDF (.pdf) - Scanned or image-based PDFs
    - Images (.png, .jpg, .jpeg, .tiff)

    **Languages:**
    - `jpn` - Japanese
    - `eng` - English
    - `eng+jpn` - Bilingual

    **Parameters:**
    - `data`: Base64 encoded file data
    - `lang`: OCR language code (default: jpn)
    - `dpi`: Resolution for PDF rendering (default: 300)

    **Response:**
    - `extracted_text`: Extracted text content
    - `page_count`: Number of pages processed
    - `language`: Language used for OCR
    - `file_type`: Type of file processed
    - `processing_time`: Processing time in seconds
    - `success`: Whether processing was successful

    **Example:**
    ```bash
    curl -X POST "http://localhost:8001/api/v1/ocr/extract-base64" \
        -H "Content-Type: application/json" \
        -d '{"data": "base64_encoded_string", "lang": "jpn", "dpi": 300}'
    ```
    """
    try:
        logger.info("Processing OCR for base64 data")

        # Decode base64 data
        file_data = base64.b64decode(request.data)

        # Create BytesIO object for the OCR service
        file_buffer = BytesIO(file_data)

        # Process with OCR service
        return OCRService.extract_text_from_file(
            file_path=file_buffer,  # type: ignore
            lang=request.lang,
            dpi=request.dpi,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing OCR from base64: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing OCR: {str(e)}",
        )


@r.post(
    "/extract-structured",
    summary="Extract Structured Data with Document AI",
    description="Extract text with entities, tables, and form fields using Google Document AI",
    response_description="Structured data extraction results",
    response_model=DocumentAIResult,
    tags=["ocr"],
)
def extract_structured_data(
    file: UploadFile = File(...),
    lang: str = Form(default=OCRConstants.DEFAULT_LANGUAGE),
) -> DocumentAIResult:
    """
    Extract structured data from uploaded PDF or image file using Google Document AI.
    
    **Supported Formats:**
    - PDF (.pdf) - Scanned or image-based PDFs
    - Images (.png, .jpg, .jpeg, .tiff)
    
    **Languages:**
    - `jpn` - Japanese
    - `eng` - English  
    - `eng+jpn` - Bilingual
    
    **Parameters:**
    - `file`: Uploaded file (PDF or image)
    - `lang`: OCR language code (default: jpn)
    
    **Response:**
    - `text`: Extracted text content
    - `confidence`: Overall confidence score
    - `entities`: Named entities (PERSON, ORGANIZATION, etc.)
    - `tables`: Extracted table structures
    - `form_fields`: Form field extractions
    - `bounding_boxes`: Text bounding boxes
    - `processing_time`: Processing time in seconds
    - `engine`: OCR engine used (document_ai)
    
    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/ocr/extract-structured" \
        -F "file=@contract.pdf" \
        -F "lang=jpn"
    ```
    """
    try:
        logger.info(f"Processing structured OCR for file: {file.filename}")

        # Validate file type
        if not file.content_type.startswith(
            (OCRConstants.SUPPORTED_PDF_TYPE, "image/")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Only PDF and image files are allowed.",
            )

        # Read file content
        file_content = file.file.read()

        # Process with Document AI service
        result = OCRService.extract_text_from_file(
            file_path=file_content, lang=lang, engine="document_ai"
        )

        # Ensure we return DocumentAIResult
        if hasattr(result, "entities"):
            return result
        else:
            # Convert OCRResult to DocumentAIResult
            from app.schemas.document_ai import DocumentAIResult

            return DocumentAIResult(
                text=result.extracted_text,
                confidence=result.confidence_score / 100,  # Convert to 0-1 scale
                entities=[],
                tables=[],
                form_fields=[],
                bounding_boxes=[],
                processing_time=result.processing_time,
                engine="document_ai",
                page_count=result.page_count,
                language=result.language,
                file_type=result.file_type,
                success=result.success,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing structured OCR: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing structured OCR: {str(e)}",
        )


@r.get(
    "/health",
    summary="OCR Service Health Check",
    description="Check the health status of the OCR service",
    response_description="Service health information",
    response_model=OCRHealthResponse,
    tags=["ocr"],
)
def health_check() -> OCRHealthResponse:
    """
    Health check endpoint for OCR service.

    **Response:**
    - `status`: Service status (healthy/unhealthy)
    - `tesseract_available`: Whether Tesseract is available
    - `jpn_language_available`: Whether Japanese language pack is available
    - `version`: Tesseract version

    **Example:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/ocr/health"
    ```
    """
    try:
        # Check Tesseract availability
        import pytesseract

        # Configure Tesseract before checking
        ocr_configured = OCRService._configure_tesseract()

        # version = pytesseract.get_tesseract_version()
        version = str(pytesseract.get_tesseract_version())

        # Check Japanese language pack
        jpn_available = True
        try:
            languages = pytesseract.get_languages()
            jpn_available = "jpn" in languages
        except Exception:
            jpn_available = False

        return OCRHealthResponse(
            status="healthy",
            tesseract_available=True,
            jpn_language_available=jpn_available,
            ocr_configured=ocr_configured,
            version=version,
        )

    except Exception as e:
        logger.error(f"OCR health check failed: {e}", exc_info=True)
        return OCRHealthResponse(
            status="unhealthy",
            tesseract_available=False,
            jpn_language_available=False,
            ocr_configured=False,
            version="unknown",
        )
