import time
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Union, Optional, List
import magic
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.core.constants import OCRConstants
from app.core.logging_config import get_logger
from app.schemas.document_ai import (
    DocumentAIResult,
    Entity,
    Table,
    FormField,
    BoundingBox,
)

logger = get_logger(__name__)

# Module-level thread pool for reuse across all document processing
_executor = ThreadPoolExecutor(
    max_workers=getattr(settings, "DOCUMENT_AI_MAX_WORKERS", 4)
)


class DocumentAIError(Exception):
    """Document AI specific errors."""

    pass


class DocumentAIPageLimitError(DocumentAIError):
    """Document AI page limit exceeded error."""

    def __init__(
        self,
        page_count: int,
        page_limit: int = settings.DOCUMENT_AI_PAGE_LIMIT,
        message: str | None = None,
    ):
        self.page_count = page_count
        self.page_limit = page_limit
        if message is None:
            message = f"Document has {page_count} pages, which exceeds the limit of {page_limit} pages. Please split the document or use a smaller file."
        super().__init__(message)


class GoogleDocumentAIService:
    """Google Document AI service for advanced document processing."""

    @classmethod
    def extract_text_from_file(
        cls, file_path: Union[str, Path, bytes, BytesIO], lang: Optional[str] = None
    ) -> DocumentAIResult:
        """Extract text using Google Document AI."""
        start_time = time.time()

        try:
            # Load file data
            file_data = cls._load_file(file_path)

            # Detect file type
            file_type = cls._detect_file_type(file_data)

            # Set default language
            if lang is None:
                lang = OCRConstants.DEFAULT_LANGUAGE

            # Process document
            result = cls._process_document(file_data, file_type, lang)

            # Calculate processing time
            processing_time = time.time() - start_time
            result.processing_time = processing_time

            logger.info(f"Document AI processing completed in {processing_time:.2f}s")
            return result

        except DocumentAIPageLimitError:
            # Propagate page limit errors so they can be converted to HTTP 400 upstream
            raise
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Document AI processing failed: {str(e)}")
            raise DocumentAIError(f"Document AI processing failed: {str(e)}")

    @staticmethod
    def _load_file(file_path: Union[str, Path, bytes, BytesIO]) -> bytes:
        """Load file into memory as bytes."""
        if isinstance(file_path, bytes):
            return file_path

        if hasattr(file_path, "read"):
            # This is a file-like object (BytesIO)
            file_like = file_path
            file_like.seek(0)  # type: ignore
            return file_like.read()

        with open(file_path, "rb") as f:
            return f.read()

    @staticmethod
    def _detect_file_type(file_data: bytes) -> str:
        """Detect file type from file data."""
        try:
            mime_type = magic.from_buffer(file_data, mime=True)

            if mime_type == "application/pdf":
                return "pdf"
            elif mime_type.startswith("image/"):
                return "image"
            else:
                return "unknown"

        except Exception as e:
            logger.warning(f"File type detection failed: {e}")
            return "unknown"

    @staticmethod
    def _process_document(
        file_data: bytes, file_type: str, lang: str
    ) -> DocumentAIResult:
        """Process document using Google Document AI with optimizations."""
        try:
            # Get processor name
            processor_name = GoogleDocumentAIService._get_processor_name()

            # Create raw document
            from google.cloud import documentai

            raw_document = documentai.RawDocument(
                content=file_data,
                mime_type=GoogleDocumentAIService._get_mime_type(file_type),
            )

            # Create process request with timeout
            request = documentai.ProcessRequest(
                name=processor_name, raw_document=raw_document
            )

            # Get client and process document with retry logic
            client = GoogleDocumentAIService._get_client()
            start_time = time.time()
            result = GoogleDocumentAIService._process_with_retry(client, request)
            processing_time = time.time() - start_time

            logger.debug(f"Document AI API call took {processing_time:.2f}s")
            document = result.document

            # Extract structured data with parallel processing
            return GoogleDocumentAIService._extract_structured_data(
                document, file_type, lang
            )

        except DocumentAIPageLimitError:
            # Let page limit errors bubble up unchanged
            raise
        except Exception as e:
            logger.error(f"Document AI processing failed: {str(e)}")
            raise DocumentAIError(f"Document AI processing failed: {str(e)}")

    @staticmethod
    @lru_cache(maxsize=1)
    def _get_client():
        """Get Document AI client (cached for performance)."""
        try:
            from google.cloud import documentai

            return documentai.DocumentProcessorServiceClient()
        except ImportError:
            raise DocumentAIError(
                "Google Cloud Document AI not installed. "
                "Install with: pip install google-cloud-documentai"
            )

    @staticmethod
    def _get_processor_name():
        """Get processor name."""
        return f"projects/{settings.GOOGLE_CLOUD_PROJECT_ID}/locations/{settings.GOOGLE_CLOUD_LOCATION}/processors/{settings.DOCUMENT_AI_PROCESSOR_ID}"

    @staticmethod
    def _process_with_retry(client, request):
        """Process document with retry logic for transient failures."""
        retry_attempts = getattr(settings, "DOCUMENT_AI_RETRY_ATTEMPTS", 3)

        for attempt in range(retry_attempts):
            try:
                return client.process_document(request=request)
            except Exception as e:
                # Check for PAGE_LIMIT_EXCEEDED error specifically
                error_str = str(e)
                if (
                    "PAGE_LIMIT_EXCEEDED" in error_str
                    or "pages exceed the limit" in error_str.lower()
                ):
                    # Extract page count and limit from error message
                    page_count = GoogleDocumentAIService._extract_page_count_from_error(
                        error_str
                    )
                    page_limit = GoogleDocumentAIService._extract_page_limit_from_error(
                        error_str
                    )
                    raise DocumentAIPageLimitError(
                        page_count=page_count,
                        page_limit=page_limit or settings.DOCUMENT_AI_PAGE_LIMIT,
                    )

                # Check if this is a retryable error
                if GoogleDocumentAIService._is_retryable_error(e):
                    if attempt == retry_attempts - 1:
                        # Last attempt, re-raise the exception
                        logger.error(
                            f"Document AI processing failed after {retry_attempts} attempts: {str(e)}"
                        )
                        raise
                    else:
                        # Wait with exponential backoff before retrying
                        wait_time = 2**attempt
                        logger.warning(
                            f"Document AI attempt {attempt + 1} failed, retrying in {wait_time}s: {str(e)}"
                        )
                        time.sleep(wait_time)
                else:
                    # Non-retryable error, re-raise immediately
                    raise

        # This should never be reached, but just in case
        raise DocumentAIError("Document AI processing failed after all retry attempts")

    @staticmethod
    def _is_retryable_error(exception):
        """Check if an exception is retryable."""
        # Common retryable Google Cloud API exceptions
        retryable_errors = [
            "ServiceUnavailable",
            "DeadlineExceeded",
            "ResourceExhausted",
            "InternalServerError",
            "Unavailable",
            "Timeout",
        ]

        error_str = str(exception)
        return any(error in error_str for error in retryable_errors)

    @staticmethod
    def _extract_page_count_from_error(error_str: str) -> int:
        """Extract page count from error message."""
        import re

        # Look for patterns like "got 3619" or "pages: 3619"
        patterns = [
            r"got\s+(\d+)",
            r"pages:\s*(\d+)",
            r"(\d+)\s+pages",
        ]
        for pattern in patterns:
            match = re.search(pattern, error_str, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 0  # Default if not found

    @staticmethod
    def _extract_page_limit_from_error(error_str: str) -> int:
        """Extract page limit from error message."""
        import re

        # Look for patterns like "limit: 30" or "page_limit: 30"
        patterns = [
            r"limit:\s*(\d+)",
            r"page_limit[:\s]+(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, error_str, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return settings.DOCUMENT_AI_PAGE_LIMIT  # Default Document AI limit

    @staticmethod
    def _get_mime_type(file_type: str) -> str:
        """Get MIME type for file type."""
        mime_types = {
            "pdf": "application/pdf",
            "image": "image/png",  # Default for images
        }
        return mime_types.get(file_type, "application/octet-stream")

    @staticmethod
    def _extract_structured_data(
        document, file_type: str, lang: str
    ) -> DocumentAIResult:
        """Extract structured data from Document AI response with parallel processing."""
        try:
            # Extract basic text first (fastest operation)
            text = document.text if document.text else ""
            page_count = len(document.pages) if document.pages else 1

            # Use module-level thread pool for parallel extraction of structured data
            # Submit all extraction tasks in parallel
            confidence_future = _executor.submit(
                GoogleDocumentAIService._calculate_confidence, document
            )
            entities_future = _executor.submit(
                GoogleDocumentAIService._extract_entities, document
            )
            tables_future = _executor.submit(
                GoogleDocumentAIService._extract_tables, document
            )
            form_fields_future = _executor.submit(
                GoogleDocumentAIService._extract_form_fields, document
            )
            bounding_boxes_future = _executor.submit(
                GoogleDocumentAIService._extract_bounding_boxes, document
            )

            # Collect results
            confidence = confidence_future.result()
            entities = entities_future.result()
            tables = tables_future.result()
            form_fields = form_fields_future.result()
            bounding_boxes = bounding_boxes_future.result()

            return DocumentAIResult(
                text=text,
                confidence=confidence,
                entities=entities,
                tables=tables,
                form_fields=form_fields,
                bounding_boxes=bounding_boxes,
                processing_time=0.0,  # Will be set by caller
                engine="document_ai",
                page_count=page_count,
                language=lang,
                file_type=file_type,
                success=True,
            )

        except Exception as e:
            logger.error(f"Structured data extraction failed: {str(e)}")
            # Return basic result on extraction failure
            return DocumentAIResult(
                text=document.text if document.text else "",
                confidence=0.0,
                entities=[],
                tables=[],
                form_fields=[],
                bounding_boxes=[],
                processing_time=0.0,
                engine="document_ai",
                page_count=1,
                language=lang,
                file_type=file_type,
                success=False,
            )

    @staticmethod
    def _calculate_confidence(document) -> float:
        """Calculate overall confidence score (optimized for performance)."""
        try:
            if not document.pages:
                return 0.0

            total_confidence = 0.0
            total_elements = 0

            for page in document.pages:
                # Prefer page-level confidence if available (O(1) per page)
                if (
                    hasattr(page, "layout")
                    and page.layout
                    and hasattr(page.layout, "confidence")
                ):
                    total_confidence += page.layout.confidence
                    total_elements += 1
                    continue

                # Fallback to element-level confidence (O(N) per page)
                if hasattr(page, "layout") and page.layout:
                    for element in page.layout.text_anchor.text_segments:
                        if hasattr(element, "confidence"):
                            total_confidence += element.confidence
                            total_elements += 1

            return total_confidence / total_elements if total_elements > 0 else 0.0

        except Exception as e:
            logger.warning(f"Confidence calculation failed: {e}")
            return 0.0

    @staticmethod
    def _extract_entities(document) -> List[Entity]:
        """Extract named entities from document."""
        entities = []

        try:
            for page in document.pages:
                if hasattr(page, "entities") and page.entities:
                    for entity in page.entities:
                        if entity.text_anchor and entity.text_anchor.text_segments:
                            # Get entity text
                            entity_text = ""
                            for segment in entity.text_anchor.text_segments:
                                start_index = segment.start_index
                                end_index = segment.end_index
                                entity_text += document.text[start_index:end_index]

                            # Create bounding box
                            bounding_box = GoogleDocumentAIService._create_bounding_box(
                                entity.bounding_poly
                            )

                            entities.append(
                                Entity(
                                    text=entity_text,
                                    type=entity.type_
                                    if hasattr(entity, "type_")
                                    else "UNKNOWN",
                                    confidence=entity.confidence
                                    if hasattr(entity, "confidence")
                                    else 0.0,
                                    bounding_box=bounding_box,
                                )
                            )
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")

        return entities

    @staticmethod
    def _extract_tables(document) -> List[Table]:
        """Extract tables from document."""
        tables = []

        try:
            for page in document.pages:
                if hasattr(page, "tables") and page.tables:
                    for table in page.tables:
                        rows = []

                        # Extract table rows
                        for row in table.body_rows:
                            row_data = []
                            for cell in row.cells:
                                cell_text = ""
                                if cell.layout and cell.layout.text_anchor:
                                    for (
                                        segment
                                    ) in cell.layout.text_anchor.text_segments:
                                        start_index = segment.start_index
                                        end_index = segment.end_index
                                        cell_text += document.text[
                                            start_index:end_index
                                        ]
                                row_data.append(cell_text.strip())
                            rows.append(row_data)

                        # Create bounding box
                        bounding_box = GoogleDocumentAIService._create_bounding_box(
                            table.bounding_poly
                        )

                        tables.append(
                            Table(
                                rows=rows,
                                confidence=table.confidence
                                if hasattr(table, "confidence")
                                else 0.0,
                                bounding_box=bounding_box,
                            )
                        )
        except Exception as e:
            logger.warning(f"Table extraction failed: {e}")

        return tables

    @staticmethod
    def _extract_form_fields(document) -> List[FormField]:
        """Extract form fields from document."""
        form_fields = []

        try:
            for page in document.pages:
                if hasattr(page, "form_fields") and page.form_fields:
                    for field in page.form_fields:
                        field_name = ""
                        field_value = ""

                        # Extract field name
                        if field.field_name and field.field_name.text_anchor:
                            for segment in field.field_name.text_anchor.text_segments:
                                start_index = segment.start_index
                                end_index = segment.end_index
                                field_name += document.text[start_index:end_index]

                        # Extract field value
                        if field.field_value and field.field_value.text_anchor:
                            for segment in field.field_value.text_anchor.text_segments:
                                start_index = segment.start_index
                                end_index = segment.end_index
                                field_value += document.text[start_index:end_index]

                        # Create bounding box
                        bounding_box = GoogleDocumentAIService._create_bounding_box(
                            field.bounding_poly
                        )

                        form_fields.append(
                            FormField(
                                field_name=field_name.strip(),
                                field_value=field_value.strip(),
                                confidence=field.confidence
                                if hasattr(field, "confidence")
                                else 0.0,
                                bounding_box=bounding_box,
                            )
                        )
        except Exception as e:
            logger.warning(f"Form field extraction failed: {e}")

        return form_fields

    @staticmethod
    def _extract_bounding_boxes(document) -> List[BoundingBox]:
        """Extract bounding boxes for text elements."""
        bounding_boxes = []

        try:
            for page in document.pages:
                if hasattr(page, "layout") and page.layout:
                    for element in page.layout.text_anchor.text_segments:
                        if hasattr(element, "bounding_poly"):
                            bounding_box = GoogleDocumentAIService._create_bounding_box(
                                element.bounding_poly
                            )
                            bounding_boxes.append(bounding_box)
        except Exception as e:
            logger.warning(f"Bounding box extraction failed: {e}")

        return bounding_boxes

    @staticmethod
    def _create_bounding_box(bounding_poly) -> BoundingBox:
        """Create bounding box from Document AI bounding poly."""
        try:
            if not bounding_poly or not bounding_poly.vertices:
                return BoundingBox(x=0, y=0, width=0, height=0)

            vertices = bounding_poly.vertices
            if len(vertices) < 2:
                return BoundingBox(x=0, y=0, width=0, height=0)

            # Get min/max coordinates
            x_coords = [v.x for v in vertices if hasattr(v, "x")]
            y_coords = [v.y for v in vertices if hasattr(v, "y")]

            if not x_coords or not y_coords:
                return BoundingBox(x=0, y=0, width=0, height=0)

            x = min(x_coords)
            y = min(y_coords)
            width = max(x_coords) - x
            height = max(y_coords) - y

            return BoundingBox(x=x, y=y, width=width, height=height)

        except Exception as e:
            logger.warning(f"Bounding box creation failed: {e}")
            return BoundingBox(x=0, y=0, width=0, height=0)
