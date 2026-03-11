from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Literal
import base64

from app.core.constants import OCRConstants


class OCRRequest(BaseModel):
    """Request schema for OCR text extraction."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_path": "/path/to/document.pdf",
                "lang": "jpn",
                "dpi": 300,
            }
        }
    )

    file_path: str = Field(..., description="Path to the file to process")
    lang: str = Field(
        default=OCRConstants.DEFAULT_LANGUAGE, description="OCR language code"
    )
    dpi: int = Field(
        default=OCRConstants.DEFAULT_DPI,
        ge=OCRConstants.MIN_DPI,
        le=OCRConstants.MAX_DPI,
        description="DPI for PDF rendering",
    )


class OCRBase64Request(BaseModel):
    """Request schema for OCR text extraction from base64 data."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": "base64_encoded_string_here",
                "lang": "jpn",
                "dpi": 300,
            }
        }
    )

    data: str = Field(..., description="Base64 encoded file data")
    lang: str = Field(
        default=OCRConstants.DEFAULT_LANGUAGE, description="OCR language code"
    )
    dpi: int = Field(
        default=OCRConstants.DEFAULT_DPI,
        ge=OCRConstants.MIN_DPI,
        le=OCRConstants.MAX_DPI,
        description="DPI for PDF rendering",
    )

    @field_validator("data")
    @classmethod
    def validate_base64(cls, v):
        """Validate that the data is valid base64."""
        try:
            base64.b64decode(v, validate=True)
            return v
        except Exception:
            raise ValueError("Invalid base64 data")


class OCRResult(BaseModel):
    """Result schema for OCR text extraction."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "extracted_text": "Sample extracted text...",
                "page_count": 1,
                "language": "jpn",
                "file_type": "image",
                "processing_time": 2.5,
                "success": True,
                "confidence_score": 85.5,
                "raw_confidence": 78.2,
                "character_count": 150,
            }
        }
    )

    extracted_text: str = Field(..., description="Extracted text content")
    page_count: int = Field(
        ..., ge=OCRConstants.MIN_PAGE_COUNT, description="Number of pages processed"
    )
    language: str = Field(..., description="Language used for OCR")
    file_type: str = Field(..., description="Type of file processed")
    processing_time: float = Field(
        ...,
        ge=OCRConstants.MIN_PROCESSING_TIME,
        description="Processing time in seconds",
    )
    success: bool = Field(..., description="Whether processing was successful")
    confidence_score: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Japanese-specific confidence score (0-100)",
    )
    raw_confidence: float = Field(
        default=0.0, ge=0, le=100, description="Raw Tesseract confidence score (0-100)"
    )
    character_count: int = Field(
        default=0, ge=0, description="Number of characters extracted"
    )


class OCRHealthResponse(BaseModel):
    """Health check response for OCR service."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "tesseract_available": True,
                "jpn_language_available": True,
                "ocr_configured": True,
                "version": "5.3.4",
            }
        }
    )

    status: Literal["healthy", "unhealthy"] = Field(..., description="Service status")
    tesseract_available: bool = Field(..., description="Whether Tesseract is available")
    jpn_language_available: bool = Field(
        ..., description="Whether Japanese language pack is available"
    )
    ocr_configured: bool = Field(
        ..., description="Whether OCR service is properly configured"
    )
    version: str = Field(..., description="Tesseract version")
