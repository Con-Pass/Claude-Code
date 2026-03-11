from typing import Optional, Dict, Any, List
import json
from redis import Redis
from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.conpass_api_service import ConpassApiService

logger = get_logger(__name__)

# Singleton Redis client for connection reuse
_redis_client: Optional[Redis] = None


def get_redis_client() -> Optional[Redis]:
    """
    Get or create a singleton Redis client with connection pooling.
    This aligns with the new embedding pipeline mechanism.
    """
    global _redis_client

    if _redis_client is None:
        try:
            _redis_client = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=False,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
        except Exception as e:
            logger.error(f"Could not initialize Redis client: {e}")
            return None

    return _redis_client


async def _fetch_contract_from_api(
    directory_ids: List[int],
    doc_id: int,
    conpass_api_service: ConpassApiService,
    include_body: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Fallback: fetch contract directly from ConPass API when not indexed in Redis.

    Args:
        directory_ids: List of directory IDs the user has access to
        doc_id: The contract_id to retrieve
        conpass_api_service: ConpassApiService instance
        include_body: Whether to also fetch the contract body text

    Returns:
        Dictionary with document_id, metadata (and full_text if include_body=True),
        or None if not found / not authorized
    """
    try:
        contract_response = await conpass_api_service.get_contract(doc_id)
        if contract_response.status != "success" or not contract_response.data:
            logger.warning(f"[API fallback] Contract {doc_id} not found in ConPass API")
            return None

        data = contract_response.data
        # Response is wrapped: {"response": {...}} or unwrapped dict
        raw = data.get("response", data) if isinstance(data, dict) else {}

        directory = raw.get("directory", {}) or {}
        directory_id = directory.get("id")

        if directory_id not in directory_ids:
            logger.warning(
                f"[API fallback] User not authorized to access contract {doc_id} "
                f"in directory {directory_id}"
            )
            return None

        metadata = {
            "directory_id": directory_id,
            "name": raw.get("name", ""),
        }

        result: Dict[str, Any] = {"document_id": doc_id, "metadata": metadata}

        if include_body:
            full_text = await conpass_api_service.get_contract_body_text(doc_id) or ""
            result["full_text"] = full_text

        logger.info(
            f"[API fallback] Fetched contract {doc_id} from ConPass API (not in Redis)"
        )
        return result

    except Exception as e:
        logger.error(f"[API fallback] Error fetching contract {doc_id}: {e}")
        return None


async def get_metadata_from_docstore(
    directory_ids: List[int],
    doc_id: int,
    conpass_api_service: Optional[ConpassApiService] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve document metadata from Redis only (without fetching contract body from API).

    This is optimized for tools that only need metadata, avoiding unnecessary API calls.
    Falls back to the ConPass API when the contract is not indexed in Redis.

    Args:
        directory_ids: List of directory IDs the user has access to
        doc_id: The contract_id to retrieve (stored as key in Redis)
        conpass_api_service: Optional ConpassApiService for API fallback

    Returns:
        Dictionary with document_id and metadata if found and authorized (no full_text)

    Note:
        - Metadata is stored in Redis for deduplication
        - Contract text is NOT fetched (use get_document_from_docstore if needed)
    """
    redis_client = get_redis_client()
    if not redis_client:
        logger.warning("Redis client not available")
        return None

    try:
        # Documents are stored with contract_id as key in Redis
        stored_data = redis_client.get(str(doc_id))

        if stored_data is None:
            logger.debug(f"Document {doc_id} not found in Redis")
            # Fallback: fetch metadata directly from ConPass API
            if conpass_api_service:
                return await _fetch_contract_from_api(
                    directory_ids, doc_id, conpass_api_service, include_body=False
                )
            return None

        # Decode bytes if needed
        if isinstance(stored_data, bytes):
            stored_data = stored_data.decode("utf-8")

        # Parse JSON data
        data = json.loads(stored_data)

        # Extract metadata and check authorization
        metadata = data.get("metadata", {})
        directory_id = metadata.get("directory_id")

        if directory_id not in directory_ids:
            logger.warning(
                f"User not authorized to access document {doc_id} in directory {directory_id}"
            )
            return None

        # Return only metadata (no API call needed)
        return {
            "document_id": doc_id,
            "metadata": metadata,
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON for document {doc_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Could not retrieve document {doc_id} from Redis: {e}")
        return None


async def get_document_from_docstore(
    directory_ids: List[int],
    doc_id: int,
    conpass_api_service: Optional[ConpassApiService] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve document metadata from Redis and fetch contract text from ConPass API.

    Falls back to fetching directly from the ConPass API when the contract is not
    indexed in Redis (e.g. newly uploaded contracts).

    Args:
        directory_ids: List of directory IDs the user has access to
        doc_id: The contract_id to retrieve (stored as key in Redis)
        conpass_api_service: ConpassApiService instance for authenticating with ConPass API

    Returns:
        Dictionary with document_id, metadata, and full_text if found and authorized

    Note:
        - Metadata (hash) is stored in Redis for deduplication
        - Contract text is fetched from ConPass API (solves 10MB Redis limit)
        - Text is URL-decoded automatically by ConpassApiService
    """
    redis_client = get_redis_client()
    if not redis_client:
        logger.warning("Redis client not available")
        return None

    try:
        # Documents are stored with contract_id as key in Redis
        stored_data = redis_client.get(str(doc_id))

        if stored_data is None:
            logger.debug(f"Document {doc_id} not found in Redis")
            # Fallback: fetch contract directly from ConPass API
            if conpass_api_service:
                return await _fetch_contract_from_api(
                    directory_ids, doc_id, conpass_api_service, include_body=True
                )
            return None

        # Decode bytes if needed
        if isinstance(stored_data, bytes):
            stored_data = stored_data.decode("utf-8")

        # Parse JSON data
        data = json.loads(stored_data)

        # Extract metadata and check authorization
        metadata = data.get("metadata", {})
        directory_id = metadata.get("directory_id")

        if directory_id not in directory_ids:
            logger.warning(
                f"User not authorized to access document {doc_id} in directory {directory_id}"
            )
            return None

        # Fetch contract text from ConPass API
        full_text = ""
        if conpass_api_service:
            api_text = await conpass_api_service.get_contract_body_text(doc_id)
            if api_text:
                full_text = api_text
                logger.debug(f"Fetched contract text from API for contract {doc_id}")
            else:
                logger.warning(f"Could not fetch contract text from API for {doc_id}")
        else:
            logger.warning(
                f"No ConPass API service provided to fetch contract text for {doc_id}"
            )

        # Return in the format expected by the tools
        return {
            "document_id": doc_id,
            "metadata": metadata,
            "full_text": full_text,
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON for document {doc_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Could not retrieve document {doc_id} from Redis: {e}")
        return None
