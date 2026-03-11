import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Tuple, IO
from dataclasses import dataclass

from google.cloud import storage
from fastapi import HTTPException

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Constants
EXTRACTED_TEXT_PREFIX = "extracted"
TEXT_FILE_EXTENSION = ".txt"
DEFAULT_MAX_WORKERS = 10
DEFAULT_ENCODING = "utf-8"


@dataclass(frozen=True)
class FileDownloadResult:
    """Result of a single file download operation."""

    file_id: str
    content: Optional[str]
    error: Optional[str]

    @property
    def is_success(self) -> bool:
        """Check if the download was successful."""
        return self.error is None and self.content is not None


class FileContentService:
    """
    Service to retrieve file content from Google Cloud Storage.

    This service provides concurrent file content retrieval capabilities,
    handling multiple file downloads efficiently using thread pools, as well
    as helpers for streaming individual files.
    """

    def __init__(self, bucket_name: Optional[str] = None):
        """
        Initialize the file content service.

        Args:
            bucket_name: Optional GCS bucket name. If not provided, uses
                        the bucket name from settings.
        """
        self.storage_client = storage.Client()
        self.bucket_name = bucket_name or settings.GCS_BUCKET_NAME
        self.bucket = self.storage_client.bucket(self.bucket_name)

    def _build_blob_path(self, file_id: str) -> str:
        """
        Build the GCS blob path for a given file ID.

        Args:
            file_id: The UUID of the file.

        Returns:
            The blob path in GCS.
        """
        return f"{EXTRACTED_TEXT_PREFIX}/{file_id}{TEXT_FILE_EXTENSION}"

    def _download_single_file(self, file_id: str) -> FileDownloadResult:
        """
        Download a single file's content from GCS.

        This method is designed to be thread-safe and used with ThreadPoolExecutor.

        Args:
            file_id: The UUID of the file to download.

        Returns:
            FileDownloadResult containing the file_id, content (if successful),
            and error message (if failed).
        """
        blob_path = self._build_blob_path(file_id)

        try:
            blob = self.bucket.blob(blob_path)

            if not blob.exists():
                error_msg = f"File not found: {blob_path}"
                logger.warning(f"File content not found for {file_id}: {blob_path}")
                return FileDownloadResult(
                    file_id=file_id, content=None, error=error_msg
                )

            content = blob.download_as_text(encoding=DEFAULT_ENCODING)
            logger.debug(f"Successfully downloaded content for {file_id}")
            return FileDownloadResult(file_id=file_id, content=content, error=None)

        except Exception as e:
            error_msg = f"Failed to retrieve file content: {str(e)}"
            logger.error(
                f"Error downloading {file_id} from {blob_path}: {e}", exc_info=True
            )
            return FileDownloadResult(file_id=file_id, content=None, error=error_msg)

    def stream_file(self, object_path: str) -> Tuple[IO[bytes], str]:
        """
        Open a file in GCS for streaming.

        Args:
            object_path: Full path of the object in the bucket.

        Returns:
            A tuple of (binary stream, content_type).

        Raises:
            HTTPException: If the blob does not exist or cannot be opened.
        """
        try:
            blob = self.bucket.blob(object_path)

            if not blob.exists():
                logger.warning(f"Requested stream for missing file: {object_path}")
                raise HTTPException(status_code=404, detail="File not found")

            stream = blob.open("rb")
            content_type = blob.content_type or "application/octet-stream"
            logger.debug(f"Opened stream for {object_path} with type {content_type}")
            return stream, content_type

        except HTTPException:
            # Re-raise FastAPI HTTP errors directly
            raise
        except Exception as e:
            logger.error(
                f"Error opening stream for {object_path}: {e}", exc_info=True
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to open file stream",
            )

    async def get_texts_by_ids(
        self, file_ids: List[str], max_workers: int = DEFAULT_MAX_WORKERS
    ) -> Dict[str, str]:
        """
        Retrieve multiple file contents concurrently from GCS.

        This method downloads file contents in parallel using a thread pool,
        providing efficient batch retrieval of file contents.

        Args:
            file_ids: List of file UUIDs to retrieve content for.
            max_workers: Maximum number of concurrent download threads.
                        Defaults to 10.

        Returns:
            Dictionary mapping file_id to content string for successful downloads.
            Only successful downloads are included in the result.

        Raises:
            HTTPException: If the file_ids list is empty, or if all downloads fail.
            ValueError: If max_workers is less than 1.
        """
        if not file_ids:
            raise HTTPException(status_code=400, detail="No file IDs provided")

        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")

        # Remove duplicates while preserving order
        unique_file_ids = list(dict.fromkeys(file_ids))
        if len(unique_file_ids) != len(file_ids):
            logger.info(
                f"Removed {len(file_ids) - len(unique_file_ids)} duplicate file IDs"
            )

        logger.info(
            f"Retrieving content for {len(unique_file_ids)} file(s) "
            f"with {max_workers} worker(s)"
        )

        # Execute downloads concurrently
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            tasks = [
                loop.run_in_executor(executor, self._download_single_file, file_id)
                for file_id in unique_file_ids
            ]
            results = await asyncio.gather(*tasks)

        # Process and categorize results
        contents: Dict[str, str] = {}
        errors: List[str] = []

        for result in results:
            if result.is_success and result.content is not None:
                contents[result.file_id] = result.content
            else:
                error_msg = result.error or "Unknown error"
                errors.append(f"{result.file_id}: {error_msg}")

        # Log warnings for partial failures
        if errors:
            logger.warning(
                f"Failed to download {len(errors)} out of {len(unique_file_ids)} file(s). "
                f"Errors: {errors}"
            )

        # Raise exception if all downloads failed
        if not contents:
            raise HTTPException(
                status_code=404,
                detail=f"Failed to retrieve content for all {len(unique_file_ids)} file(s). "
                f"Errors: {errors[:5]}",  # Show first 5 errors
            )

        successful_file_ids = list(contents.keys())
        logger.info(
            f"Successfully retrieved content for {len(contents)} out of "
            f"{len(unique_file_ids)} file(s): {successful_file_ids}"
        )

        return contents
