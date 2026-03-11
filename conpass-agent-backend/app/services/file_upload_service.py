import base64
import json
import mimetypes
import os
import uuid
import tiktoken
import urllib.parse
from datetime import timedelta
from typing import Tuple, List

from fastapi import UploadFile, HTTPException
from google.cloud import storage
from google.oauth2 import service_account

from app.core.config import settings
from app.core.environment_flags import is_development
from app.core.logging_config import get_logger
from app.schemas.upload import DocumentFile, FileUploadResult
from app.services.ocr_service import OCRService
from app.services.google_document_ai_service import DocumentAIPageLimitError

logger = get_logger(__name__)


class FileUploadService:
    """
    Service to handle file uploads, text extraction, token validation, and GCS storage.
    """

    @classmethod
    async def process_file(
        cls,
        file: UploadFile,
    ) -> DocumentFile:
        """
        Process an uploaded file: extract text, validate tokens, and upload to GCS.
        """
        file_content = await file.read()
        file_name = file.filename or "unknown"
        file_type = (
            file.content_type
            or mimetypes.guess_type(file_name)[0]
            or "application/octet-stream"
        )

        # 1. Extract text locally
        try:
            extracted_text = cls._extract_text_content(
                file_content, file_name, file_type
            )
        except HTTPException:
            raise
        except DocumentAIPageLimitError as e:
            logger.warning(f"Document page limit exceeded for {file_name}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Text extraction failed for {file_name}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to extract text from file: {str(e)}"
            )

        # 2. Token Validation
        cls._validate_token_count(extracted_text)

        # 3. Upload to GCS
        file_id = str(uuid.uuid4())

        # Upload original file
        safe_name = cls._get_safe_filename(file_name)
        file_gcs_path = f"files/{file_id}/{safe_name}"
        file_public_url = cls._upload_to_gcs(file_content, file_gcs_path, file_type)

        # Upload extracted text: extracted/{file_id}.txt
        text_filename = f"{file_id}.txt"
        text_gcs_path = f"extracted/{text_filename}"
        text_public_url = cls._upload_to_gcs(
            extracted_text.encode("utf-8"), text_gcs_path, "text/plain"
        )

        # 4. Construct Response
        return DocumentFile(
            id=file_id,
            file_name=file_name,
            content_type=file_type,
            file_url=file_public_url,
            extracted_text_url=text_public_url,
            token_count=cls._count_tokens(extracted_text),
        )

    @classmethod
    async def process_files(
        cls,
        files: List[UploadFile],
    ) -> List[FileUploadResult]:
        """
        Process multiple uploaded files: extract text, validate tokens, and upload to GCS.
        Returns a list of DocumentFile objects.
        """
        if not files:
            return []

        results: List[FileUploadResult] = []

        # Process files sequentially to keep behavior simple and predictable.
        # This can be optimized later with concurrency if needed.
        for file in files:
            file_name = file.filename or "unknown"
            try:
                document = await cls.process_file(file)
                results.append(
                    FileUploadResult(
                        file_name=file_name,
                        success=True,
                        document=document,
                        error=None,
                    )
                )
            except HTTPException as e:
                detail = e.detail if isinstance(e.detail, str) else str(e.detail)
                logger.warning(
                    f"File processing failed for {file_name} with HTTPException: {detail}"
                )
                results.append(
                    FileUploadResult(
                        file_name=file_name,
                        success=False,
                        document=None,
                        error=detail,
                    )
                )
            except Exception as e:
                logger.error(f"File processing failed for {file_name}: {e}")
                results.append(
                    FileUploadResult(
                        file_name=file_name,
                        success=False,
                        document=None,
                        error="Internal error while processing file.",
                    )
                )

        return results

    @classmethod
    def process_base64_file(
        cls,
        file_name: str,
        base64_content: str,
    ) -> DocumentFile:
        """
        Process a base64 encoded file (Legacy support).
        """
        file_content, extension = cls._preprocess_base64_file(base64_content)
        # Mocking an UploadFile-like object or refactoring logic to share code.
        # For simplicity, we'll duplicate core logic or create a shared internal method.
        # Let's create a shared method taking bytes.

        return cls._process_file_bytes(file_content, file_name, extension)

    @classmethod
    def _extract_text_content(
        cls, content: bytes, file_name: str, content_type: str
    ) -> str:
        """
        Extract text based on file type.
        """
        # 1. PDF / Images -> Document AI
        if content_type == "application/pdf" or content_type.startswith("image/"):
            return OCRService.extract_text_from_file(content, engine="document_ai").text  # type: ignore

        # 2. Word (.docx) -> docx2txt
        # Check strict mime or extension
        if (
            content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or file_name.endswith(".docx")
        ):
            try:
                import docx2txt
                import io

                # docx2txt.process accepts a file-like object
                return docx2txt.process(io.BytesIO(content))
            except ImportError:
                logger.error("docx2txt not installed")
                raise HTTPException(500, "docx2txt dependency missing for Word files.")

        # 3. CSV / Text -> Simple Decode
        # Check strict mime or extension
        if content_type in ["text/csv", "text/plain"] or file_name.endswith(
            (".csv", ".txt")
        ):
            return content.decode("utf-8", errors="ignore")

        # 4. Excel -> Pandas
        if (
            content_type
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            or file_name.endswith(".xlsx")
        ):
            try:
                import pandas as pd
                import io

                # Read Excel from bytes
                df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
                # Convert to string (handling NaN as empty)
                return df.to_string(index=False, na_rep="")
            except ImportError as e:
                logger.error(f"Pandas/OpenPyXL not installed: {e}")
                raise HTTPException(500, "Pandas dependency missing for Excel files.")
            except Exception as e:
                logger.error(f"Excel extraction failed: {e}")
                raise HTTPException(500, f"Failed to extract text from Excel: {str(e)}")

        # Fallback / Unsupported
        # Previously we used Tesseract here, but requirement is to NOT use it.
        # We raise 400 for unsupported types.
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Supported: PDF, Image, DOCX, CSV, TXT.",
        )

    @classmethod
    def _process_file_bytes(
        cls, file_content: bytes, file_name: str, extension: str
    ) -> DocumentFile:
        # Determine mime type from extension
        mime_type = mimetypes.types_map.get(f".{extension}", "application/octet-stream")

        # 1. Extract text (Reusing the dedicated method)
        try:
            extracted_text = cls._extract_text_content(
                file_content, file_name, mime_type
            )
        except HTTPException:
            raise
        except DocumentAIPageLimitError as e:
            logger.warning(f"Document page limit exceeded for {file_name}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to extract text: {str(e)}"
            )

        # 2. Token Validation
        cls._validate_token_count(extracted_text)

        # 3. Upload to GCS
        file_id = str(uuid.uuid4())

        file_gcs_path = f"files/{file_id}/{cls._get_safe_filename(file_name)}"
        file_public_url = cls._upload_to_gcs(file_content, file_gcs_path, mime_type)

        text_filename = f"{file_id}.txt"
        text_gcs_path = f"extracted/{text_filename}"
        text_public_url = cls._upload_to_gcs(
            extracted_text.encode("utf-8"), text_gcs_path, "text/plain"
        )

        return DocumentFile(
            id=file_id,
            file_name=file_name,
            content_type=extension,
            file_url=file_public_url,
            extracted_text_url=text_public_url,
            token_count=cls._count_tokens(extracted_text),
        )

    @staticmethod
    def _validate_token_count(text: str):
        count = FileUploadService._count_tokens(text)
        logger.info(f"Token count: {count}")
        if count > settings.UPLOAD_MAX_TOKENS:
            raise HTTPException(
                status_code=400,
                detail=f"Token limit exceeded. File has {count} tokens, limit is {settings.UPLOAD_MAX_TOKENS}.",
            )

    @staticmethod
    def _count_tokens(text: str) -> int:
        try:
            encoding = tiktoken.get_encoding(settings.TIKTOKEN_ENCODING)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Tiktoken encoding failed, defaulting to 0: {e}")
            return 0

    @staticmethod
    def _upload_to_gcs(
        content: bytes, destination_blob_name: str, content_type: str
    ) -> str:
        """
        Uploads a file to the bucket and returns the URL for serving.
        - In development only: if ASSET_DELIVERY_MODE is "cdn" and CDN_DOMAIN is set,
        returns CDN URL (https://{CDN_DOMAIN}/{path}).
        - Otherwise returns a time-limited signed URL for GCS (private objects).
        """
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(settings.GCS_BUCKET_NAME)
            blob = bucket.blob(destination_blob_name)

            blob.upload_from_string(content, content_type=content_type)

            use_cdn = getattr(settings, "ASSET_DELIVERY_MODE", "gcs") == "cdn" and bool(
                getattr(settings, "CDN_DOMAIN", None)
            )
            ttl_seconds = getattr(settings, "SIGNED_URL_TTL_SECONDS", 3600)

            if is_development() and use_cdn:
                # CDN URL only in development for now (LB → FastAPI → GCS).
                return f"https://{settings.CDN_DOMAIN}/{destination_blob_name}"

            # Signed URL for private GCS (staging/production, or when CDN not configured).
            # Prefer explicit signing credentials from GCP_SA_KEY if available
            signing_creds = None
            key_json = os.environ.get("GCP_SA_KEY")
            if key_json:
                try:
                    info = json.loads(key_json)
                    signing_creds = (
                        service_account.Credentials.from_service_account_info(info)
                    )
                except Exception as e:
                    logger.error(f"Failed to load GCP_SA_KEY for signing: {e}")

            return blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=ttl_seconds),
                method="GET",
                credentials=signing_creds,
            )

        except Exception as e:
            logger.error(f"GCS Upload failed: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to upload file to storage."
            )

    @staticmethod
    def _preprocess_base64_file(base64_content: str) -> Tuple[bytes, str]:
        if "," in base64_content:
            header, data = base64_content.split(",", 1)
            mime_type = header.split(";")[0].split(":", 1)[1]
            extension = mimetypes.guess_extension(mime_type)
            if extension:
                extension = extension.lstrip(".")
            else:
                extension = "bin"
        else:
            data = base64_content
            extension = "bin"

        return base64.b64decode(data), extension

    @staticmethod
    def _get_safe_filename(file_name: str) -> str:
        """
        Returns a URL-safe version of the filename, handling non-ASCII characters.
        """
        return urllib.parse.quote(file_name)
