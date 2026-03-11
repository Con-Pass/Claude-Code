import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from typing import Tuple, Union, Dict, List, Optional

import numpy as np
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import magic

from app.core.config import settings
from app.core.constants import OCRConstants
from app.core.logging_config import get_logger
from app.schemas.ocr import OCRResult

logger = get_logger(__name__)


class TesseractOCRService:
    """
    Tesseract OCR Service for extracting text from PDFs and images.
    """

    @classmethod
    def extract_text_from_file(
        cls,
        file_path: Union[str, Path, bytes, BytesIO],
        lang: Optional[str] = None,
        dpi: Optional[int] = None,
    ) -> OCRResult:
        """
        Extract text from PDF or image file using Tesseract OCR.

        Args:
            file_path: Path to file, file bytes, or BytesIO object
            lang: OCR language code (jpn, eng, eng+jpn)
            dpi: Resolution for PDF rendering

        Returns:
            OCRResult with extracted text and metadata
        """
        # Use provided parameters or defaults
        if lang is None:
            lang = OCRConstants.DEFAULT_LANGUAGE

        start_time = time.time()

        try:
            # Configure Tesseract
            cls._configure_tesseract()

            # Load and validate file
            file_data = cls._load_file(file_path)
            cls._validate_file(file_data)

            # Detect file type first
            file_type = cls._detect_file_type(file_data)

            # Determine optimal DPI if not provided
            if dpi is None:
                dpi = TesseractOCRService._get_optimal_dpi(file_data, lang, file_type)

            if file_type == "pdf":
                extracted_text, page_count, confidence_data = (
                    cls._process_pdf_with_confidence(file_data, lang, dpi)
                )
            else:
                extracted_text, page_count, confidence_data = (
                    cls._process_image_with_confidence(file_data, lang)
                )

            processing_time = time.time() - start_time

            return OCRResult(
                extracted_text=extracted_text,
                page_count=page_count,
                language=lang,
                file_type=file_type,
                processing_time=round(processing_time, 2),
                success=True,
                confidence_score=confidence_data.get("confidence", 0.0),
                raw_confidence=confidence_data.get("raw_confidence", 0.0),
                character_count=confidence_data.get("character_count", 0),
            )

        except Exception as e:
            logger.error(f"Tesseract OCR processing failed: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def _configure_tesseract() -> bool:
        """Configure Tesseract with custom path and data prefix.

        Returns:
            bool: True if configuration was successful, False otherwise
        """
        try:
            # Set Tesseract executable path
            if hasattr(settings, "TESSERACT_PATH") and settings.TESSERACT_PATH:
                pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
                logger.debug(f"Tesseract path set to: {settings.TESSERACT_PATH}")

            # Set Tesseract data prefix for language packs
            if hasattr(settings, "TESSDATA_PREFIX") and settings.TESSDATA_PREFIX:
                os.environ["TESSDATA_PREFIX"] = settings.TESSDATA_PREFIX
                logger.debug(
                    f"Tesseract data prefix set to: {settings.TESSDATA_PREFIX}"
                )
            return True
        except Exception as e:
            logger.warning(f"Failed to configure Tesseract: {e}")
            return False

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
    def _validate_file(file_data: bytes) -> None:
        """Validate file size and type."""
        max_size = settings.OCR_MAX_FILE_MB * 1024 * 1024
        if len(file_data) > max_size:
            raise ValueError(f"File too large. Max size: {max_size} bytes")

    @staticmethod
    def _detect_file_type(file_data: bytes) -> str:
        """Detect file type from content using python-magic for robust detection."""
        try:
            mime_type = magic.from_buffer(file_data, mime=True)
            logger.debug(f"Detected file type: {mime_type}")

            # Handle PDF files
            if mime_type == OCRConstants.SUPPORTED_PDF_TYPE:
                return OCRConstants.FILE_TYPE_PDF

            # Handle image files
            elif mime_type.startswith("image/"):
                return OCRConstants.FILE_TYPE_IMAGE

            # Fallback: Check file signatures for common image types
            elif mime_type == "application/octet-stream":
                if file_data.startswith(b"\x89PNG"):  # PNG signature
                    return OCRConstants.FILE_TYPE_IMAGE
                elif file_data.startswith(b"\xff\xd8\xff"):  # JPEG signature
                    return OCRConstants.FILE_TYPE_IMAGE
                elif file_data.startswith(b"II*\x00") or file_data.startswith(
                    b"MM\x00*"
                ):  # TIFF signature
                    return OCRConstants.FILE_TYPE_IMAGE
                elif file_data.startswith(b"%PDF"):  # PDF signature
                    return OCRConstants.FILE_TYPE_PDF

            raise ValueError(f"Unsupported file type: {mime_type}")
        except Exception as e:
            logger.error(f"Failed to detect file type: {e}")
            raise ValueError("Unable to determine file type")

    @staticmethod
    def _process_pdf_with_confidence(
        file_data: bytes, lang: str, dpi: int
    ) -> Tuple[str, int, Dict]:
        """Process PDF file and extract text with confidence scores (optimized with parallel processing)."""
        try:
            # Convert PDF to images
            images = convert_from_bytes(file_data, dpi=dpi)

            # Use parallel processing for better performance
            return TesseractOCRService._process_pdf_parallel(images, lang)

        except Exception as e:
            logger.error(f"PDF processing with confidence failed: {str(e)}")
            raise

    @staticmethod
    def _process_pdf_parallel(
        images: List[Image.Image], lang: str
    ) -> Tuple[str, int, Dict]:
        """Process PDF pages in parallel for better performance."""
        try:
            extracted_text = ""
            all_confidences: List[float] = []
            all_raw_confidences: List[float] = []
            total_characters = 0

            # Use ThreadPoolExecutor for parallel processing
            max_workers = min(OCRConstants.MAX_PARALLEL_WORKERS, len(images))

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all pages for processing
                future_to_page = {
                    executor.submit(
                        TesseractOCRService._extract_with_confidence, image, lang
                    ): i
                    for i, image in enumerate(images)
                }

                # Collect results in order
                results = [None] * len(images)
                for future in as_completed(future_to_page):
                    page_idx = future_to_page[future]
                    try:
                        results[page_idx] = future.result()  # type: ignore
                    except Exception as e:
                        logger.error(f"Page {page_idx + 1} processing failed: {e}")
                        results[page_idx] = {  # type: ignore
                            "text": "",
                            "confidence": 0.0,
                            "raw_confidence": 0.0,
                            "character_count": 0,
                        }

            # Process results in order
            for i, confidence_data in enumerate(results):
                if confidence_data:
                    page_text = confidence_data["text"]
                    extracted_text += f"\n--- Page {i + 1} ---\n{page_text}\n"

                    # Collect confidence data
                    all_confidences.append(confidence_data["confidence"])
                    all_raw_confidences.append(confidence_data["raw_confidence"])
                    total_characters += confidence_data["character_count"]

            # Calculate average confidence
            avg_confidence = (
                sum(all_confidences) / len(all_confidences) if all_confidences else 0
            )
            avg_raw_confidence = (
                sum(all_raw_confidences) / len(all_raw_confidences)
                if all_raw_confidences
                else 0
            )

            return (
                extracted_text.strip(),
                len(images),
                {
                    "confidence": avg_confidence,
                    "raw_confidence": avg_raw_confidence,
                    "character_count": total_characters,
                },
            )

        except Exception as e:
            logger.error(f"Parallel PDF processing failed: {str(e)}")
            raise

    @staticmethod
    def _process_image_with_confidence(
        file_data: bytes, lang: str
    ) -> Tuple[str, int, Dict]:
        """Process image file and extract text with confidence scores."""
        try:
            # Load image
            image = Image.open(BytesIO(file_data))

            # Extract with confidence
            confidence_data = TesseractOCRService._extract_with_confidence(image, lang)

            return (
                confidence_data["text"].strip(),
                1,
                {
                    "confidence": confidence_data["confidence"],
                    "raw_confidence": confidence_data["raw_confidence"],
                    "character_count": confidence_data["character_count"],
                },
            )

        except Exception as e:
            logger.error(f"Image processing with confidence failed: {str(e)}")
            raise

    @staticmethod
    def _extract_with_confidence(image: Image.Image, lang: str) -> Dict:
        """Extract text with confidence scores for Japanese OCR (optimized single call)."""
        try:
            # Get detailed data including confidence scores
            data = pytesseract.image_to_data(
                image,
                lang=lang,
                output_type=pytesseract.Output.DICT,
                config="--psm 6",  # Uniform block of text
            )

            # Calculate confidence metrics
            confidences = [int(conf) for conf in data["conf"] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            # Extract text from data instead of separate call
            extracted_text = " ".join([word for word in data["text"] if word.strip()])
            character_count = len([c for c in extracted_text if c.strip()])

            # Japanese-specific confidence factors
            japanese_confidence = TesseractOCRService._calculate_japanese_confidence(
                data, confidences
            )

            return {
                "text": extracted_text,
                "confidence": japanese_confidence,
                "raw_confidence": avg_confidence,
                "character_count": character_count,
                "data": data,
            }
        except Exception as e:
            logger.error(f"Confidence extraction failed: {str(e)}")
            # Fallback to simple text extraction
            try:
                fallback_text = pytesseract.image_to_string(image, lang=lang)
                return {
                    "text": fallback_text,
                    "confidence": 0.0,
                    "raw_confidence": 0.0,
                    "character_count": len([c for c in fallback_text if c.strip()]),
                    "data": {},
                }
            except Exception as fallback_error:
                logger.error(f"Fallback text extraction failed: {str(fallback_error)}")
                return {
                    "text": "",
                    "confidence": 0.0,
                    "raw_confidence": 0.0,
                    "character_count": 0,
                    "data": {},
                }

    @staticmethod
    def _get_optimal_dpi(file_data: bytes, lang: str, file_type: str) -> int:
        """Determine optimal DPI based on PDF content analysis."""
        if not OCRConstants.ADAPTIVE_DPI_ENABLED or file_type != "pdf":
            return OCRConstants.DEFAULT_DPI

        try:
            # Quick preview at low DPI to assess content
            preview_images = convert_from_bytes(
                file_data, dpi=150, first_page=1, last_page=1
            )
            if not preview_images:
                return OCRConstants.DEFAULT_DPI

            preview_image = preview_images[0]

            # Analyze content characteristics
            if TesseractOCRService._is_text_dense(preview_image):
                return OCRConstants.DPI_STRATEGIES["text_dense"]
            elif TesseractOCRService._is_image_heavy(preview_image):
                return OCRConstants.DPI_STRATEGIES["image_heavy"]
            else:
                return OCRConstants.DPI_STRATEGIES["text_normal"]

        except Exception as e:
            logger.warning(f"DPI analysis failed, using default: {e}")
            return OCRConstants.DEFAULT_DPI

    @staticmethod
    def _is_text_dense(image: Image.Image) -> bool:
        """Check if image contains dense text (many small characters)."""
        try:
            # Quick OCR to assess text density
            data = pytesseract.image_to_data(
                image, output_type=pytesseract.Output.DICT, config="--psm 6"
            )

            # Count words and characters
            words = [word for word in data["text"] if word.strip()]
            total_chars = sum(len(word) for word in words)

            # Dense text has many characters per word on average
            if words and total_chars > 0:
                avg_chars_per_word = total_chars / len(words)
                return avg_chars_per_word > 3.0 and len(words) > 20
            return False

        except Exception:
            return False

    @staticmethod
    def _is_image_heavy(image: Image.Image) -> bool:
        """Check if image is primarily visual content."""
        try:
            # Analyze image characteristics
            width, height = image.size
            total_pixels = width * height

            # Convert to grayscale for analysis
            gray_image = image.convert("L")

            # Calculate variance (high variance = more visual content)
            img_array = np.array(gray_image)
            variance = np.var(img_array)

            # High variance and large size suggests image-heavy content
            return variance > 2000 and total_pixels > 1000000

        except Exception:
            return False

    @staticmethod
    def _calculate_japanese_confidence(data: Dict, confidences: List[int]) -> float:
        """Calculate Japanese-specific confidence score."""
        try:
            # Weight factors for Japanese OCR
            weights = {
                "hiragana_accuracy": 0.3,
                "katakana_accuracy": 0.3,
                "kanji_accuracy": 0.4,
            }

            # Analyze character types
            text = "".join(data["text"])
            hiragana_chars = len([c for c in text if "\u3040" <= c <= "\u309f"])
            katakana_chars = len([c for c in text if "\u30a0" <= c <= "\u30ff"])
            kanji_chars = len([c for c in text if "\u4e00" <= c <= "\u9faf"])

            # Calculate weighted confidence
            total_chars = hiragana_chars + katakana_chars + kanji_chars
            if total_chars == 0:
                return 0

            # Apply Japanese-specific confidence calculation
            japanese_confidence = (
                (
                    weights["hiragana_accuracy"] * (hiragana_chars / total_chars)
                    + weights["katakana_accuracy"] * (katakana_chars / total_chars)
                    + weights["kanji_accuracy"] * (kanji_chars / total_chars)
                )
                * (sum(confidences) / len(confidences))
                if confidences
                else 0
            )

            return min(100, max(0, japanese_confidence))
        except Exception as e:
            logger.error(f"Japanese confidence calculation failed: {str(e)}")
            return 0.0
