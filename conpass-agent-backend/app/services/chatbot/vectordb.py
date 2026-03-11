from llama_index.vector_stores.qdrant import QdrantVectorStore

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def get_vector_store():
    collection_name = settings.QDRANT_COLLECTION
    url = settings.QDRANT_URL
    api_key = settings.QDRANT_API_KEY
    if not collection_name or not url:
        raise ValueError(
            "Please set QDRANT_COLLECTION, QDRANT_URL"
            " to your environment variables or config them in the .env file"
        )
    return QdrantVectorStore(
        collection_name=collection_name,
        url=url,
        api_key=api_key,
    )
