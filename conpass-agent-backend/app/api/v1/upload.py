from typing import Optional, List
import urllib.parse

from fastapi import APIRouter, HTTPException, UploadFile, File, Body, Request, status
from fastapi.responses import StreamingResponse
from app.core.logging_config import get_logger
from app.services.file_upload_service import FileUploadService
from app.services.file_content_service import FileContentService
from app.schemas.upload import FileUploadRequest, FileUploadResult

file_upload_router = r = APIRouter()

logger = get_logger(__name__)


@r.post(
    "",
    summary="Upload File",
    description="Upload one or more files for document processing, token validation, and storage.",
    response_description="List of document file information including CDN URLs",
    response_model=List[FileUploadResult],
    tags=["upload"],
)
async def upload_file(
    file: Optional[List[UploadFile]] = File(
        None, description="One or more files to upload (Multipart)"
    ),
    request: Optional[FileUploadRequest] = Body(
        None, description="Base64 encoded file (Legacy)"
    ),
) -> List[FileUploadResult]:
    """
    Upload one or more files for processing.

    Supports two modes:
    1. **Multipart/Form-Data**: Preferred for standard file uploads. Supports multiple files.
    2. **Base64 JSON**: Legacy support (`{"base64": "...", "name": "..."}`) for a single file.

    The process includes:
    - Text extraction (OCR/Document AI)
    - Token counting & Limit validation
    - Storage to Google Cloud Storage
    - Response with CDN URLs

    **Response:**
    Each item in the response list contains:
    - `id`: Unique file ID
    - `file_name`: Original file name
    - `content_type`: File MIME type
    - `file_url`: CDN URL to the file
    - `extracted_text_url`: CDN URL to the extracted text
    - `token_count`: Token count of the extracted text
    """
    try:
        # Mode 1: Multipart (one or more files)
        if file:
            logger.info(f"Processing multipart files: {[f.filename for f in file]}")
            results = await FileUploadService.process_files(file)

            # If only one file was uploaded and it failed, surface the error as HTTP 400
            if len(results) == 1 and not results[0].success:
                raise HTTPException(
                    status_code=400,
                    detail=results[0].error or "Failed to process file.",
                )

            # If all files failed, return HTTP 400 with a generic message
            if results and all(not r.success for r in results):
                raise HTTPException(
                    status_code=400,
                    detail="None of the uploaded files could be processed.",
                )

            return results

        # Mode 2: Base64 (single file, legacy)
        elif request:
            logger.info(f"Processing base64 file: {request.name}")
            try:
                document = FileUploadService.process_base64_file(
                    request.name, request.base64
                )
                return [
                    FileUploadResult(
                        file_name=request.name,
                        success=True,
                        document=document,
                        error=None,
                    )
                ]
            except HTTPException as e:
                detail = e.detail if isinstance(e.detail, str) else str(e.detail)
                # For legacy single-file uploads, surface the error as HTTP 400
                raise HTTPException(status_code=e.status_code, detail=detail)

        else:
            raise HTTPException(
                status_code=400,
                detail="No file provided. Send either 'file' as multipart/form-data or JSON body with 'base64'.",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing file")


@r.get("/{file_id}/{filename}")
def serve_file(
    file_id: str,
    filename: str,
    request: Request,
):
    # Middleware populates request.state.conpass_token after basic validation.
    conpass_jwt = getattr(request.state, "conpass_token", None)
    if not conpass_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing ConPass authentication token.",
        )

    # GCS object uses URL-escaped filename (same as upload path)
    safe_filename = urllib.parse.quote(filename)
    object_path = f"files/{file_id}/{safe_filename}"
    logger.info(f"Streaming file: {object_path}")
    file_content_service = FileContentService()
    stream, content_type = file_content_service.stream_file(object_path)

    return StreamingResponse(
        stream,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=3600",
        },
    )
