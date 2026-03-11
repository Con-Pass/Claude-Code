from io import BytesIO
from pathlib import Path
from typing import Union, Optional

from app.core.logging_config import get_logger
from app.schemas.ocr import OCRResult
from app.schemas.document_ai import DocumentAIResult
from app.services.tesseract_ocr_service import TesseractOCRService
from app.services.google_document_ai_service import (
    GoogleDocumentAIService,
    DocumentAIPageLimitError,
)

logger = get_logger(__name__)


class OCRService:
    """
    Unified OCR Service that can use either Tesseract or Google Document AI.
    """

    @classmethod
    def extract_text_from_file(
        cls,
        file_path: Union[str, Path, bytes, BytesIO],
        lang: Optional[str] = None,
        dpi: Optional[int] = None,
        engine: str = "document_ai",
    ) -> Union[OCRResult, DocumentAIResult]:
        """
        Extract text from PDF or image file using specified OCR engine.

        Args:
            file_path: Path to file, file bytes, or BytesIO object
            lang: OCR language code (jpn, eng, eng+jpn)
            dpi: Resolution for PDF rendering (Tesseract only)
            engine: OCR engine to use ("tesseract" or "document_ai")

        Returns:
            OCRResult or DocumentAIResult with extracted text and metadata
        """
        try:
            logger.info(f"OCR processing started with engine: {engine}")

            if engine == "tesseract":
                return TesseractOCRService.extract_text_from_file(file_path, lang, dpi)
            elif engine == "document_ai":
                return GoogleDocumentAIService.extract_text_from_file(file_path, lang)
            else:
                raise ValueError(
                    f"Unsupported engine: {engine}. Use 'tesseract' or 'document_ai'"
                )

        except DocumentAIPageLimitError:
            # Re-raise page limit errors as-is so they can be caught upstream
            raise
        except Exception as e:
            logger.error(f"OCR processing failed: {str(e)}")
            raise

    @classmethod
    def get_normalized_confidence(
        cls, result: Union[OCRResult, DocumentAIResult]
    ) -> float:
        """
        OCR結果から正規化された信頼度スコア（0.0〜1.0）を返す。

        Tesseract: confidence_score (0-100) を 0.0-1.0 に変換
        Document AI: confidence (0.0-1.0) をそのまま返す

        Args:
            result: OCR処理結果

        Returns:
            正規化された信頼度スコア（0.0〜1.0）
        """
        if isinstance(result, DocumentAIResult):
            return result.confidence
        elif isinstance(result, OCRResult):
            return result.confidence_score / 100.0
        return 0.0
