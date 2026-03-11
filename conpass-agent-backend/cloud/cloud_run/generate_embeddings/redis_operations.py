from typing import Any, Dict, Optional
from doc_store import get_redis_client
import json
import logging

logger = logging.getLogger(__name__)


def check_redis_document(contract_id: int) -> Optional[Dict[str, Any]]:
    """
    Check if document exists in Redis and return stored data.

    Args:
        contract_id: Contract ID

    Returns:
        Dictionary with 'metadata' and 'hash' if exists, None otherwise
        Note: 'text' field is no longer stored in Redis (fetched from ConPass API when needed)
    """
    try:
        redis_client = get_redis_client()
        if not redis_client:
            logger.error("Redis client not available")
            return None

        stored_data = redis_client.get(str(contract_id))
        if stored_data is None:
            return None

        # Decode bytes if needed
        if isinstance(stored_data, bytes):
            stored_data = stored_data.decode("utf-8")

        return json.loads(stored_data)
    except Exception as e:
        logger.error(f"Error checking Redis for contract {contract_id}: {e}")
        return None


def store_redis_document(
    contract_id: int, metadata: Dict[str, Any], hash_value: str
) -> bool:
    """
    Store document metadata and hash in Redis (text is not stored).

    Args:
        contract_id: Contract ID
        metadata: Document metadata dictionary
        hash_value: Computed hash of text+metadata

    Returns:
        True if successful, False otherwise

    Raises:
        RuntimeError: If Redis client is unavailable or storage fails

    Note:
        Contract text is no longer stored in Redis to avoid 10MB size limits.
        Text is fetched from ConPass API when needed by agent tools.
    """
    try:
        redis_client = get_redis_client()
        if not redis_client:
            raise RuntimeError("Redis client not available - cannot store document")

        data = {"metadata": metadata, "hash": hash_value}

        redis_client.set(str(contract_id), json.dumps(data))
        return True
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Error storing document in Redis for contract {contract_id}: {e}")
        raise RuntimeError(
            f"Failed to store document in Redis for contract {contract_id}: {e}"
        ) from e
