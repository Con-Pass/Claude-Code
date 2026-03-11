from pydantic import BaseModel
from typing import Any, Optional


class FileUploadRequest(BaseModel):
    base64: str
    name: str
    params: Any = None


class DocumentFile(BaseModel):
    id: str
    file_name: str
    content_type: Optional[str] = None
    file_url: Optional[str] = None
    extracted_text_url: Optional[str] = None
    token_count: Optional[int] = None


class FileUploadResult(BaseModel):
    """
    Per-file result for multi-file uploads.
    """

    file_name: str
    success: bool
    document: Optional[DocumentFile] = None
    error: Optional[str] = None
