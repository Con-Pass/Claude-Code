from pydantic import BaseModel, Field, ConfigDict
from typing import List
from app.core.constants import OCRConstants


class BoundingBox(BaseModel):
    """Bounding box coordinates for text elements."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"x": 100, "y": 200, "width": 300, "height": 50}}
    )

    x: float = Field(..., description="X coordinate of top-left corner")
    y: float = Field(..., description="Y coordinate of top-left corner")
    width: float = Field(..., description="Width of the bounding box")
    height: float = Field(..., description="Height of the bounding box")


class Entity(BaseModel):
    """Named entity from Document AI."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "田中太郎",
                "type": "PERSON",
                "confidence": 0.95,
                "bounding_box": {"x": 100, "y": 200, "width": 100, "height": 20},
            }
        }
    )

    text: str = Field(..., description="Entity text")
    type: str = Field(
        ..., description="Entity type (PERSON, ORGANIZATION, LOCATION, etc.)"
    )
    confidence: float = Field(..., ge=0, le=1, description="Entity confidence score")
    bounding_box: BoundingBox = Field(..., description="Entity bounding box")


class Table(BaseModel):
    """Extracted table structure."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rows": [["名前", "年齢", "住所"], ["田中太郎", "30", "東京都"]],
                "confidence": 0.90,
                "bounding_box": {"x": 50, "y": 100, "width": 400, "height": 200},
            }
        }
    )

    rows: List[List[str]] = Field(..., description="Table rows and columns")
    confidence: float = Field(..., ge=0, le=1, description="Table confidence score")
    bounding_box: BoundingBox = Field(..., description="Table bounding box")


class FormField(BaseModel):
    """Form field extraction."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "field_name": "氏名",
                "field_value": "田中太郎",
                "confidence": 0.88,
                "bounding_box": {"x": 200, "y": 150, "width": 150, "height": 25},
            }
        }
    )

    field_name: str = Field(..., description="Form field name")
    field_value: str = Field(..., description="Form field value")
    confidence: float = Field(..., ge=0, le=1, description="Field confidence score")
    bounding_box: BoundingBox = Field(..., description="Field bounding box")


class DocumentAIResult(BaseModel):
    """Result schema for Google Document AI processing."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "契約書の内容...",
                "confidence": 0.95,
                "entities": [
                    {
                        "text": "田中太郎",
                        "type": "PERSON",
                        "confidence": 0.95,
                        "bounding_box": {
                            "x": 100,
                            "y": 200,
                            "width": 100,
                            "height": 20,
                        },
                    }
                ],
                "tables": [],
                "form_fields": [],
                "bounding_boxes": [],
                "processing_time": 2.5,
                "engine": "document_ai",
                "page_count": 1,
                "language": "jpn",
                "file_type": "pdf",
                "success": True,
            }
        }
    )

    text: str = Field(..., description="Extracted text content")
    confidence: float = Field(..., ge=0, le=1, description="Overall confidence score")
    entities: List[Entity] = Field(default=[], description="Named entities")
    tables: List[Table] = Field(default=[], description="Extracted tables")
    form_fields: List[FormField] = Field(default=[], description="Form fields")
    bounding_boxes: List[BoundingBox] = Field(
        default=[], description="Text bounding boxes"
    )
    processing_time: float = Field(..., ge=0, description="Processing time in seconds")
    engine: str = Field(default="document_ai", description="OCR engine used")
    page_count: int = Field(
        default=1,
        ge=OCRConstants.MIN_PAGE_COUNT,
        description="Number of pages processed",
    )
    language: str = Field(
        default=OCRConstants.DEFAULT_LANGUAGE, description="Language used for OCR"
    )
    file_type: str = Field(..., description="Type of file processed")
    success: bool = Field(..., description="Whether processing was successful")


class DocumentAIRequest(BaseModel):
    """Request schema for Document AI processing."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"file_path": "/path/to/document.pdf", "lang": "jpn"}
        }
    )

    file_path: str = Field(..., description="Path to the file to process")
    lang: str = Field(
        default=OCRConstants.DEFAULT_LANGUAGE, description="OCR language code"
    )


class DocumentAIBase64Request(BaseModel):
    """Request schema for Document AI processing from base64 data."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"data": "base64_encoded_string_here", "lang": "jpn"}
        }
    )

    data: str = Field(..., description="Base64 encoded file data")
    lang: str = Field(
        default=OCRConstants.DEFAULT_LANGUAGE, description="OCR language code"
    )
