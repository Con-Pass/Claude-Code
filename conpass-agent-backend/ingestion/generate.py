# flake8: noqa: E402
from dotenv import load_dotenv

load_dotenv()

from app.core.logging_config import get_logger

from llama_index.core.ingestion import DocstoreStrategy, IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.settings import Settings
from llama_index.core.storage import StorageContext
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.storage.docstore.redis import RedisDocumentStore
from llama_index.storage.kvstore.redis import RedisKVStore

# from cloud.cloud_functions.generate_embeddings.doc_generator import get_documents

from ingestion.doc_generator import get_documents
from app.services.chatbot.vectordb import get_vector_store
from app.core.model_settings import init_model_settings
from app.core.config import settings as app_settings


logger = get_logger(__name__)

STORAGE_DIR = app_settings.STORAGE_DIR


def get_doc_store():
    import os

    # If the storage directory is there, load the document store from it.
    # If not, set up an in-memory document store since we can't load from a directory that doesn't exist.
    if os.path.exists(STORAGE_DIR):
        return SimpleDocumentStore.from_persist_dir(STORAGE_DIR)
    else:
        return SimpleDocumentStore()


def get_redis_doc_store():
    import os
    from redis import Redis
    from redis.asyncio import Redis as AsyncRedis

    redis_client = Redis.from_url(os.environ["REDIS_URL"])
    async_redis_client = AsyncRedis.from_url(os.environ["REDIS_URL"])

    kvstore = RedisKVStore(
        redis_client=redis_client, async_redis_client=async_redis_client
    )

    docstore = RedisDocumentStore(redis_kvstore=kvstore, namespace="document_store")

    return docstore


def run_pipeline(docstore, vector_store, documents):
    pipeline = IngestionPipeline(
        transformations=[
            SentenceSplitter(
                chunk_size=Settings.chunk_size,
                chunk_overlap=Settings.chunk_overlap,
            ),
            Settings.embed_model,
        ],
        docstore=docstore,
        docstore_strategy=DocstoreStrategy.UPSERTS_AND_DELETE,  # type: ignore
        vector_store=vector_store,
    )

    nodes = pipeline.run(show_progress=True, documents=documents)

    return nodes


def persist_storage(docstore, vector_store):
    storage_context = StorageContext.from_defaults(
        docstore=docstore,
        vector_store=vector_store,
    )
    storage_context.persist(STORAGE_DIR)


def generate_datasource():
    init_model_settings()
    logger.info("Generate index for the provided data")

    # Get the stores and documents or create new ones
    documents = get_documents()
    # Set private=false to mark the document as public (required for filtering)
    for doc in documents:
        doc.metadata["private"] = "false"
    docstore = get_redis_doc_store()
    vector_store = get_vector_store()

    # Run the ingestion pipeline
    _ = run_pipeline(docstore, vector_store, documents)

    # Build the index and persist storage
    # persist_storage(docstore, vector_store)

    logger.info("Finished generating the index")


if __name__ == "__main__":
    generate_datasource()
