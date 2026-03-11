from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from embedding_pipeline_config import embedding_pipeline_config
from llama_index.storage.docstore.redis import RedisDocumentStore
from llama_index.storage.kvstore.redis import RedisKVStore
from typing import Optional

# Singleton instances for connection reuse
_redis_client: Optional[Redis] = None
_async_redis_client: Optional[AsyncRedis] = None
_docstore: Optional[RedisDocumentStore] = None


def _initialize_redis_clients() -> None:
    """Create Redis clients if they are not already initialized."""
    global _redis_client, _async_redis_client

    if _redis_client is None:
        _redis_client = Redis.from_url(
            embedding_pipeline_config.REDIS_URL,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )

    if _async_redis_client is None:
        _async_redis_client = AsyncRedis.from_url(
            embedding_pipeline_config.REDIS_URL,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )


def get_redis_doc_store() -> RedisDocumentStore:
    """
    Get or create a singleton Redis document store with connection pooling.
    Reuses connections across requests for better concurrency.
    """
    global _docstore

    if _docstore is None:
        # Create clients with connection pooling enabled
        _initialize_redis_clients()

        kvstore = RedisKVStore(
            redis_client=_redis_client, async_redis_client=_async_redis_client
        )

        _docstore = RedisDocumentStore(
            redis_kvstore=kvstore, namespace="document_store"
        )

    return _docstore


def get_redis_client() -> Redis:
    """Expose the shared Redis client for auxiliary Redis operations."""
    _initialize_redis_clients()
    return _redis_client
