import logging
import asyncio
from typing import List, Tuple, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

from embedding_pipeline_config import embedding_pipeline_config

logger = logging.getLogger(__name__)

# Singleton Qdrant client for connection reuse
_qdrant_client: Optional[QdrantClient] = None
# Async lock to prevent race conditions when creating indexes
_index_creation_lock = asyncio.Lock()
# Track if indexes have been ensured to avoid repeated checks
_indexes_ensured = False


PayloadIndex = Tuple[str, models.PayloadSchemaType]


PAYLOAD_INDEXES: List[PayloadIndex] = [
    ("name", models.PayloadSchemaType.KEYWORD),
    ("directory_id", models.PayloadSchemaType.INTEGER),
    ("contract_id", models.PayloadSchemaType.INTEGER),
    ("private", models.PayloadSchemaType.BOOL),
    ("契約書名_title", models.PayloadSchemaType.KEYWORD),
    ("会社名_甲_company_a", models.PayloadSchemaType.KEYWORD),
    ("会社名_乙_company_b", models.PayloadSchemaType.KEYWORD),
    ("会社名_丙_company_c", models.PayloadSchemaType.KEYWORD),
    ("会社名_丁_company_d", models.PayloadSchemaType.KEYWORD),
    ("契約種別_contract_type", models.PayloadSchemaType.KEYWORD),
    ("裁判所_court", models.PayloadSchemaType.KEYWORD),
    ("契約日_contract_date", models.PayloadSchemaType.DATETIME),
    ("契約開始日_contract_start_date", models.PayloadSchemaType.DATETIME),
    ("契約終了日_contract_end_date", models.PayloadSchemaType.DATETIME),
    ("契約終了日_cancel_notice_date", models.PayloadSchemaType.DATETIME),
    ("自動更新の有無_auto_update", models.PayloadSchemaType.BOOL),
    # 契約種別 3階層タクソノミー
    ("contract_category", models.PayloadSchemaType.KEYWORD),
    ("contract_type", models.PayloadSchemaType.KEYWORD),
    ("contract_subtype", models.PayloadSchemaType.KEYWORD),
    ("classification_method", models.PayloadSchemaType.KEYWORD),
    # 関連契約ID
    ("related_contract_id", models.PayloadSchemaType.INTEGER),
]


def _get_qdrant_client() -> QdrantClient:
    """
    Get or create a singleton Qdrant client.
    Reuses connection across requests for better concurrency.
    """
    global _qdrant_client

    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            url=embedding_pipeline_config.QDRANT_URL,
            api_key=embedding_pipeline_config.QDRANT_API_KEY,
        )

    return _qdrant_client


async def ensure_payload_indexes() -> None:
    """
    Idempotently create the payload indexes required for metadata filtering.
    Uses async lock to prevent race conditions when multiple requests run concurrently.
    """
    global _indexes_ensured

    # Fast path: if indexes are already ensured, skip the lock
    if _indexes_ensured:
        return

    # Use lock to ensure only one request creates indexes at a time
    async with _index_creation_lock:
        # Double-check after acquiring lock
        if _indexes_ensured:
            return

        collection_name = embedding_pipeline_config.QDRANT_COLLECTION
        client = _get_qdrant_client()

        try:
            collection_info = client.get_collection(collection_name=collection_name)
            existing_schema = collection_info.payload_schema or {}
        except Exception as exc:
            logger.warning(
                "Unable to fetch payload schema for collection %s: %s",
                collection_name,
                exc,
            )
            existing_schema = {}

        for field_name, schema_type in PAYLOAD_INDEXES:
            existing_definition = existing_schema.get(field_name)
            if (
                existing_definition is not None
                and existing_definition.data_type == schema_type
            ):
                logger.debug("Payload index for %s already exists", field_name)
                continue

            try:
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=schema_type,
                )
                logger.info(
                    "Created payload index for %s (%s)",
                    field_name,
                    schema_type.value,
                )
            except Exception as exc:
                if "already exists" in str(exc):
                    logger.debug("Payload index for %s already existed", field_name)
                    continue

                logger.error(
                    "Failed to create payload index for %s: %s", field_name, exc
                )
                raise

        # Mark indexes as ensured after successful creation
        _indexes_ensured = True
        logger.info("Payload indexes ensured successfully")
