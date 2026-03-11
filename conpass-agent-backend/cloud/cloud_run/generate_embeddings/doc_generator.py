import logging
from typing import List, Dict, Any
from llama_index.core import Document
import base64
import json
from urllib.parse import unquote
from bs4 import BeautifulSoup
from metadata_map import get_metadata
from doc_store import get_redis_client
from qdrant__operations import delete_qdrant_points_by_contract_id

from summary_generator import generate_summary
import datetime


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that converts datetime/date objects to strings."""

    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)


logger = logging.getLogger(__name__)
SKIPPED_CONTRACTS_HASH_KEY = "embedding_skipped_contracts"


def _log_skipped_contract(id: str, contract: Dict[str, Any], reason: str) -> None:
    """Record contracts that could not be embedded along with the reason."""
    try:
        redis_client = get_redis_client()
        if redis_client:
            payload = json.dumps({"contract": contract, "reason": reason})
            redis_client.hset(SKIPPED_CONTRACTS_HASH_KEY, id, payload)
    except Exception as redis_error:
        logger.error(
            "Failed to log skipped contract %s for reason %s: %s",
            id,
            reason,
            redis_error,
        )


def get_documents_from_pubsub(envelope: Dict[str, Any]) -> List[Document]:
    """
    Extract and parse documents from a Pub/Sub push message envelope.

    Args:
        envelope: The Pub/Sub message envelope received via HTTP POST

    Returns:
        List of Document objects parsed from the batch
    """
    try:
        # Pub/Sub push messages have this structure:
        # {
        #   "message": {
        #     "data": "base64-encoded-string",
        #     "messageId": "...",
        #     "publishTime": "..."
        #   },
        #   "subscription": "..."
        # }

        message = envelope.get("message")
        if not message:
            logger.error("No 'message' field in Pub/Sub envelope")
            return []

        encoded_data = message.get("data")
        if not encoded_data:
            logger.error("No 'data' field in Pub/Sub message")
            return []

        # Decode the base64-encoded message data
        batch_json = base64.b64decode(encoded_data).decode("utf-8")
        batch = json.loads(batch_json)
        logger.info(
            f"Received batch: {json.dumps(batch, ensure_ascii=False, cls=DateTimeEncoder)}"
        )
        logger.info(
            f"Received batch {batch['batch_number']} with {batch['contracts_count']} contracts"
        )

        docs = []

        event_type = batch.get("event_type")

        if event_type == "deleted":
            for contract_id in batch["contract_ids"]:
                try:
                    # Delete from Qdrant first (primary searchable data - critical to remove)
                    delete_qdrant_points_by_contract_id(contract_id)

                    # Delete from Redis second (cache/deduplication layer - less critical)
                    redis_client = get_redis_client()
                    if redis_client:
                        deleted_count = redis_client.delete(str(contract_id))
                        if deleted_count > 0:
                            logger.info(
                                f"Deleted Redis document for contract {contract_id}"
                            )
                        else:
                            logger.warning(
                                f"Redis key not found for contract {contract_id} (may have already been deleted)"
                            )

                except Exception as e:
                    logger.error(f"Error deleting contract {contract_id}: {e}")
                    _log_skipped_contract(
                        contract_id, {"id": contract_id}, "deletion_error"
                    )
                    continue

            # Return early after processing deletions - no embeddings to generate
            logger.info(f"Processed deletion of {len(batch['contract_ids'])} contracts")
            return []

        for contract in batch["contracts"]:
            try:
                contract_id = contract.get("id")
                body_raw = contract.get("body")
                directory = contract.get("directory")

                if not contract_id:
                    logger.warning(f"No contract id found for contract {contract}")
                    continue

                if not body_raw:
                    logger.warning(f"No body found for contract {contract_id}")
                    # _log_skipped_contract(contract_id, contract, "missing_body")
                    continue

                if not directory:
                    logger.warning(f"No directory found for contract {contract_id}")
                    # _log_skipped_contract(contract_id, contract, "missing_directory")
                    continue

                decoded = unquote(body_raw)  # URL decode
                text = BeautifulSoup(decoded, "html.parser").get_text(strip=True)

                # Validate text is a non-empty string
                if not text or not isinstance(text, str) or len(text.strip()) == 0:
                    logger.warning(
                        f"Invalid or empty text for contract {contract_id} (text type: {type(text)}, length: {len(text) if isinstance(text, str) else 'N/A'})"
                    )
                    # _log_skipped_contract(contract_id, contract, "empty_text")
                    continue

                # Ensure text is a string and properly encoded
                text = str(text).strip()
                if len(text) == 0:
                    logger.warning(
                        f"Text is empty after stripping for contract {contract_id}"
                    )
                    # _log_skipped_contract(
                    #     contract_id, contract, "empty_text_after_strip"
                    # )
                    continue

                directory_id = directory.get("id")
                if not directory_id:
                    logger.warning(
                        "No directory id found for contract %s (directory=%s)",
                        contract_id,
                        directory,
                    )
                    # _log_skipped_contract(contract_id, contract, "missing_directory_id")
                    continue

                summary = generate_summary(text)

                contract_name = contract.get("name")
                contract_metadata = contract.get("metadata", [])

                metadata = get_metadata(contract_metadata)

                metadata["contract_id"] = contract_id
                metadata["name"] = contract_name
                metadata["directory_id"] = directory_id

                if summary:
                    metadata["summary"] = summary

                # 契約種別 3階層分類
                try:
                    from contract_classifier import classify_contract
                    existing_type = metadata.get("契約種別_contract_type")
                    classification = classify_contract(
                        name=contract_name or "",
                        text=text,
                        existing_type=existing_type,
                        use_llm=True,
                    )
                    metadata.update(classification)
                except Exception as cls_err:
                    logger.warning(
                        f"Contract {contract_id}: classification failed: {cls_err}"
                    )

                # metadata = {
                #     "id": contract_id,
                #     "name": contract["name"],
                #     "directory_id": directory_id
                # }

                # for item in contract["metadata"]:
                #     metadata[item["label"]] = item["value"]

                docs.append(
                    Document(
                        id_=str(contract_id),
                        text=text,
                        metadata=metadata,
                    )
                )

            except Exception as e:
                contract_id = contract.get("id")
                if not contract_id:
                    logger.warning(f"No contract id found for contract {contract}")
                    continue
                logger.error(f"Error processing contract {contract_id}: {e}")
                _log_skipped_contract(contract_id, contract, "processing_error")
                continue

        return docs

    except Exception as e:
        logger.error(f"Error processing contracts: {e}")
        return []
