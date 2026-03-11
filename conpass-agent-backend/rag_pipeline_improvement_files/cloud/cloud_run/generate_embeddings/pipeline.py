from dotenv import load_dotenv

import logging
import time
from typing import Any, Dict, List
from uuid import uuid4
from llama_index.core import Document
from chunker import chunk_text, chunk_text_with_metadata
from hash import compute_document_hash
from qdrant__operations import (
    delete_qdrant_points_by_contract_id,
)
from redis_operations import (
    check_redis_document,
    store_redis_document,
)
from embedding_pipeline_config import embedding_pipeline_config
from vector_db import get_qdrant_vector_store, CustomQdrantVectorStore
from model import get_embedding_model
from schema import VectorStoreNode
from pipeline_metrics import (
    record_document_processed,
    record_chunks_per_document,
    record_batch_time,
    check_alerts,
)

load_dotenv()


logger = logging.getLogger(__name__)

# エラーハンドリング設定
DOCUMENT_TIMEOUT_SECONDS = 60
FAILURE_RATE_THRESHOLD = 0.05  # 5%以上の失敗率でDLQ行き


def generate_datasource(documents: List[Document]) -> Dict[str, Any]:
    """
    Generate embeddings for the provided documents using custom pipeline with hash-based deduplication.
    Note: ensure_payload_indexes() should be called separately before this function
    to avoid race conditions. It's now handled in main.py at startup.

    Returns:
        Dict with processing results: {nodes, processed, failed, skipped, updated, failures}
    """
    logger.info("Generate index for the provided data")

    for doc in documents:
        doc.metadata["private"] = False

    # Use custom pipeline with hash-based deduplication
    result = run_custom_pipeline(documents)

    return result


def process_document(
    document: Document,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model,
    vector_store: CustomQdrantVectorStore,
) -> List[VectorStoreNode]:
    """
    Process a single document: chunk, embed, and store in Qdrant.

    Args:
        document: LlamaIndex Document object
        chunk_size: Maximum size of each chunk (in characters)
        chunk_overlap: Number of characters to overlap between chunks
        embedding_model: Embedding model instance
        vector_store: CustomQdrantVectorStore instance

    Returns:
        List of CustomNode objects created
    """
    # Get document text and metadata
    text = document.get_content()
    metadata = document.metadata.copy()

    # Chunk the document text with structural metadata
    chunks_with_meta = chunk_text_with_metadata(text, chunk_size, chunk_overlap)

    if not chunks_with_meta:
        raise ValueError(
            f"No chunks created for document {document.id_} - text may be empty or too short"
        )

    # Create CustomNode objects for each chunk with structural metadata
    nodes: List[VectorStoreNode] = []
    for chunk_content, struct_meta in chunks_with_meta:
        node_metadata = metadata.copy()
        # 構造メタデータを付与（None値はスキップ）
        if struct_meta.get("article_number") is not None:
            node_metadata["article_number"] = struct_meta["article_number"]
        if struct_meta.get("clause_number") is not None:
            node_metadata["clause_number"] = struct_meta["clause_number"]
        if struct_meta.get("section_title"):
            node_metadata["section_title"] = struct_meta["section_title"]

        node = VectorStoreNode(
            node_id=str(uuid4()),
            text=chunk_content,
            metadata=node_metadata,
        )
        nodes.append(node)

    contract_id = metadata.get("contract_id", "unknown")
    logger.info(
        f"Created {len(nodes)} chunks for contract {contract_id} (document {document.id_})"
    )

    # Generate embeddings for each node
    texts = [node.text for node in nodes]
    embeddings = embedding_model.get_text_embedding_batch(texts)

    # Get contract_id for logging (all nodes have the same contract_id from the document)
    contract_id = metadata.get("contract_id", "unknown")

    # Validate and attach embeddings to nodes - fail fast on any error
    for node, embedding in zip(nodes, embeddings):
        if embedding is None:
            raise ValueError(
                f"Dense embedding generation failed for contract {contract_id} (node {node.node_id}) - returned None"
            )

        # Ensure embedding is a list and not empty
        if not isinstance(embedding, (list, tuple)) or len(embedding) == 0:
            raise ValueError(
                f"Invalid dense embedding format for contract {contract_id} (node {node.node_id}) - "
                f"expected non-empty list/tuple, got {type(embedding)}"
            )

        node.embedding = embedding

    # Add nodes to vector store
    vector_store.add(nodes)

    logger.info(
        f"Processed contract {contract_id} (document {document.id_}): created {len(nodes)} nodes"
    )
    return nodes


def _process_single_document_safely(
    document: Document,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model,
    vector_store: CustomQdrantVectorStore,
) -> Dict[str, Any]:
    """
    単一ドキュメントを安全に処理する。
    エラーが発生してもバッチ全体を停止せず、失敗を記録する。

    Returns:
        {"status": "new"|"updated"|"skipped"|"failed", "nodes": [...], "error": str|None}
    """
    contract_id_raw = document.metadata.get("contract_id")
    if contract_id_raw is None:
        return {
            "status": "failed",
            "contract_id": "unknown",
            "nodes": [],
            "error": f"Document {document.id_} missing contract_id in metadata",
        }

    try:
        contract_id = int(contract_id_raw)
    except (ValueError, TypeError) as e:
        return {
            "status": "failed",
            "contract_id": str(contract_id_raw),
            "nodes": [],
            "error": f"Invalid contract_id '{contract_id_raw}': {e}",
        }

    start_time = time.monotonic()

    try:
        text = document.get_content()
        metadata = document.metadata.copy()

        # Compute hash
        current_hash = compute_document_hash(text, metadata)

        # Check Redis
        stored_data = check_redis_document(contract_id)

        if stored_data is None:
            # New document
            logger.info(f"New document {contract_id}, processing...")
            nodes = process_document(
                document, chunk_size, chunk_overlap, embedding_model, vector_store
            )

            if not store_redis_document(contract_id, metadata, current_hash):
                logger.error(
                    f"Failed to store document {contract_id} in Redis after Qdrant update"
                )

            elapsed = time.monotonic() - start_time
            logger.info(f"Document {contract_id} processed in {elapsed:.1f}s")
            return {
                "status": "new",
                "contract_id": contract_id,
                "nodes": nodes,
                "error": None,
            }

        elif stored_data.get("hash") == current_hash:
            # Hash matches - document unchanged, skip
            logger.info(f"Document {contract_id} unchanged (hash matches), skipping...")
            return {
                "status": "skipped",
                "contract_id": contract_id,
                "nodes": [],
                "error": None,
            }

        else:
            # Hash differs - document updated
            logger.info(
                f"Document {contract_id} updated (hash differs), reprocessing..."
            )
            delete_qdrant_points_by_contract_id(contract_id)

            nodes = process_document(
                document, chunk_size, chunk_overlap, embedding_model, vector_store
            )

            if not store_redis_document(contract_id, metadata, current_hash):
                logger.error(
                    f"Failed to update document {contract_id} in Redis after Qdrant update"
                )

            elapsed = time.monotonic() - start_time
            logger.info(f"Document {contract_id} updated in {elapsed:.1f}s")
            return {
                "status": "updated",
                "contract_id": contract_id,
                "nodes": nodes,
                "error": None,
            }

    except Exception as e:
        elapsed = time.monotonic() - start_time
        error_msg = f"Error processing contract {contract_id}: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": "failed",
            "contract_id": contract_id,
            "nodes": [],
            "error": error_msg,
            "elapsed_seconds": elapsed,
        }


def run_custom_pipeline(documents: List[Document]) -> Dict[str, Any]:
    """
    Run custom ingestion pipeline with hash-based deduplication.
    ドキュメント単位のエラー分離により、1件の失敗がバッチ全体を停止しない。

    Args:
        documents: List of Document objects to process

    Returns:
        Dict with processing results including nodes, counts, and failure details
    """
    logger.info(f"Starting custom pipeline for {len(documents)} documents")

    # Initialize components
    chunk_size = embedding_pipeline_config.CHUNK_SIZE
    chunk_overlap = embedding_pipeline_config.CHUNK_OVERLAP
    embedding_model = get_embedding_model()
    vector_store = get_qdrant_vector_store()

    all_nodes = []
    processed_count = 0
    skipped_count = 0
    updated_count = 0
    failed_count = 0
    failures: List[Dict[str, Any]] = []

    batch_start = time.monotonic()

    for document in documents:
        result = _process_single_document_safely(
            document, chunk_size, chunk_overlap, embedding_model, vector_store
        )

        status = result["status"]
        all_nodes.extend(result["nodes"])

        record_document_processed(status)
        if result["nodes"]:
            record_chunks_per_document(len(result["nodes"]))

        if status == "new":
            processed_count += 1
        elif status == "skipped":
            skipped_count += 1
        elif status == "updated":
            updated_count += 1
        elif status == "failed":
            failed_count += 1
            failures.append({
                "contract_id": result["contract_id"],
                "error": result["error"],
            })

    batch_elapsed = time.monotonic() - batch_start
    total_docs = len(documents)

    # 失敗率の計算とログ
    failure_rate = failed_count / total_docs if total_docs > 0 else 0.0

    logger.info(
        f"Pipeline completed in {batch_elapsed:.1f}s: "
        f"{processed_count} new, {updated_count} updated, "
        f"{skipped_count} skipped, {failed_count} failed, "
        f"{len(all_nodes)} total nodes "
        f"(failure rate: {failure_rate:.1%})"
    )

    if failure_rate > FAILURE_RATE_THRESHOLD:
        logger.warning(
            f"Failure rate {failure_rate:.1%} exceeds threshold "
            f"{FAILURE_RATE_THRESHOLD:.1%}. "
            f"Failed contracts: {[f['contract_id'] for f in failures]}"
        )

    # メトリクス記録
    record_batch_time(batch_elapsed * 1000)

    # アラートチェック
    alerts = check_alerts()
    for alert in alerts:
        logger.warning(alert)

    if failures:
        for f in failures:
            logger.warning(
                f"Failed contract {f['contract_id']}: {f['error']}"
            )

    return {
        "nodes": all_nodes,
        "processed": processed_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "failure_rate": failure_rate,
        "failures": failures,
        "batch_elapsed_seconds": batch_elapsed,
    }
