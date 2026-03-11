"""Docstore utilities for retrieving documents."""

from typing import Optional, Dict, Any
import os

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def get_docstore():
    """Get the Redis docstore instance."""
    try:
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            logger.warning("REDIS_URL not set in environment variables")
            return None

        from redis import Redis
        from redis.asyncio import Redis as AsyncRedis
        from llama_index.storage.docstore.redis import RedisDocumentStore
        from llama_index.storage.kvstore.redis import RedisKVStore

        redis_client = Redis.from_url(redis_url)
        async_redis_client = AsyncRedis.from_url(redis_url)
        kvstore = RedisKVStore(
            redis_client=redis_client, async_redis_client=async_redis_client
        )
        return RedisDocumentStore(redis_kvstore=kvstore, namespace="document_store")
    except Exception as e:
        logger.warning(f"Could not initialize docstore: {e}")
        return None


async def get_document_from_docstore(doc_id: str) -> Optional[Dict[str, Any]]:
    """Try to get the full document from docstore."""
    docstore = get_docstore()
    if not docstore:
        return None

    try:
        doc = docstore.get_document(doc_id)
        if doc:
            return {
                "document_id": doc_id,
                "metadata": doc.metadata,
                "full_text": doc.text,
            }
    except Exception as e:
        logger.warning(f"Could not retrieve document {doc_id} from docstore: {e}")
    return None
