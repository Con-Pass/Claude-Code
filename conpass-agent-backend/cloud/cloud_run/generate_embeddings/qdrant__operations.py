import logging
from qdrant_client.http import models
from embedding_pipeline_config import embedding_pipeline_config
from qdrant_indexes import _get_qdrant_client

logger = logging.getLogger(__name__)


def delete_qdrant_points_by_contract_id(contract_id: int) -> None:
    """
    Delete all Qdrant points associated with a document ID.
    Uses contract_id (integer) field in payload to filter.

    Args:
        contract_id: Contract ID to delete
    """
    try:
        qdrant_client = _get_qdrant_client()
        collection_name = embedding_pipeline_config.QDRANT_COLLECTION

        conditions = []

        conditions.append(
            models.FieldCondition(
                key="contract_id", match=models.MatchValue(value=contract_id)
            )
        )

        filter_condition = models.Filter(should=conditions)

        qdrant_client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(filter=filter_condition),
        )

        logger.info(f"Deleted Qdrant points for contract {contract_id}")
    except Exception as e:
        logger.error(f"Error deleting Qdrant points for contract {contract_id}: {e}")
