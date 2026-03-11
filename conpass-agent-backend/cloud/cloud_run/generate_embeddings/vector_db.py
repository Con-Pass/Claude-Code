import logging
from typing import List, Optional, Dict, Any, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http import models

from schema import VectorStoreNode
from embedding_pipeline_config import embedding_pipeline_config
from qdrant_indexes import _get_qdrant_client
from sparse_model import generate_sparse_embeddings_batch

logger = logging.getLogger(__name__)

# Singleton instance for connection reuse
_vector_store: Optional["CustomQdrantVectorStore"] = None


class CustomQdrantVectorStore:
    """
    Custom Qdrant vector store that provides full control over how nodes are stored.
    Unlike LlamaIndex's QdrantVectorStore, this allows you to customize the storage format.

    This implementation stores:
    - Dense vectors (from OpenAI embeddings) for semantic similarity
    - Sparse vectors (BM25-style via FastEmbed) for keyword-style matching, to enable
      production-ready hybrid dense + sparse search in Qdrant.
    """

    def __init__(
        self,
        collection_name: Optional[str] = None,
        qdrant_client: Optional[QdrantClient] = None,
    ):
        """
        Initialize custom Qdrant vector store.

        Args:
            collection_name: Name of the Qdrant collection. If None, uses config default.
            qdrant_client: QdrantClient instance. If None, uses singleton from qdrant_indexes.

        Note:
            The Qdrant collection must be configured with named vectors:
            - "dense": Dense vector (OpenAI embeddings) - required
            - "sparse": Sparse vector (BM25 embeddings) - required for hybrid search
            The collection should be created separately before using this vector store.
        """
        self.collection_name = (
            collection_name or embedding_pipeline_config.QDRANT_COLLECTION
        )
        self.client = qdrant_client or _get_qdrant_client()
        logger.info(
            f"CustomQdrantVectorStore initialized for collection: {self.collection_name}"
        )
        # Verify collection exists and has correct configuration
        self._verify_collection_config()

    def _verify_collection_config(self) -> None:
        """
        Verify that the Qdrant collection exists and is configured correctly for hybrid search.
        Logs warnings if configuration is incorrect but doesn't raise exceptions.
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)
            vectors_config = collection_info.config.params.vectors

            # Check if collection uses named vectors (required for hybrid search)
            if not hasattr(vectors_config, "named") or not vectors_config.named:
                logger.warning(
                    f"Collection {self.collection_name} does not use named vectors. "
                    "Hybrid search requires named vectors with 'dense' and 'sparse'."
                )
                return

            # Check for dense vector
            if "dense" not in vectors_config.named:
                logger.warning(
                    f"Collection {self.collection_name} missing 'dense' named vector. "
                    "This is required for dense embeddings."
                )
            else:
                logger.debug(
                    f"Collection {self.collection_name} has 'dense' vector configured"
                )

            # Check for sparse vector (required)
            if "sparse" not in vectors_config.named:
                logger.error(
                    f"Collection {self.collection_name} missing 'sparse' named vector. "
                    "Sparse vectors are required for hybrid search."
                )
            else:
                sparse_config = vectors_config.named["sparse"]
                if not isinstance(sparse_config, models.SparseVectorParams):
                    logger.warning(
                        f"Collection {self.collection_name} 'sparse' vector is not configured "
                        "as a SparseVectorParams. Hybrid search may not work correctly."
                    )
                else:
                    logger.debug(
                        f"Collection {self.collection_name} has 'sparse' vector configured"
                    )

        except Exception as e:
            logger.warning(
                f"Could not verify collection configuration for {self.collection_name}: {e}. "
                "Collection may not exist yet or may be created separately."
            )

    def _build_sparse_vector(self, text: str) -> models.SparseVector:
        """
        Build a sparse vector from text using BM25-style embeddings via FastEmbed.

        This provides production-ready keyword matching with proper IDF weighting
        and length normalization, enabling high-quality hybrid search in Qdrant.

        Args:
            text: Input text to generate sparse embedding for

        Returns:
            Qdrant SparseVector with indices and values

        Raises:
            ValueError: If text is empty or sparse embedding generation fails
        """
        if not text or not text.strip():
            raise ValueError("Empty text provided for sparse vector generation")

        try:
            # Use batch function for consistency (even for single text)
            results = generate_sparse_embeddings_batch([text])
            if not results or results[0] is None:
                raise ValueError("Failed to generate sparse embedding for text")

            indices, values = results[0]
            if not indices or not values:
                raise ValueError("Empty sparse embedding indices/values")

            return models.SparseVector(indices=indices, values=values)
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error generating sparse vector: {e}", exc_info=True)
            raise ValueError(f"Failed to generate sparse vector: {e}") from e

    def _node_to_point(self, node: VectorStoreNode) -> models.PointStruct:
        """
        Convert a VectorStoreNode to a Qdrant point.
        Customize this method to control how nodes are stored.

        Args:
            node: VectorStoreNode instance

        Returns:
            Qdrant PointStruct
        """
        # Get embedding - ensure it's a list
        embedding = node.embedding
        contract_id = node.metadata.get("contract_id", "unknown")
        if embedding is None:
            raise ValueError(
                f"Contract {contract_id} (node {node.node_id}) has no embedding"
            )

        # Convert embedding to list if it's not already
        if not isinstance(embedding, list):
            embedding = list(embedding)

        # Build payload from node metadata
        # Customize this section to control what metadata is stored
        payload: Dict[str, Any] = {}

        # Store text content
        payload["text"] = node.text

        # Store all metadata from node
        metadata = node.metadata
        if metadata:
            # Copy metadata to payload
            for key, value in metadata.items():
                # Handle different value types appropriately
                if value is not None:
                    payload[key] = value

        # Store node ID in payload for reference
        payload["node_id"] = node.node_id

        # Build sparse vector for hybrid search (required)
        sparse_vector = self._build_sparse_vector(node.text)

        # Build vector dict with both dense and sparse vectors (both required)
        vector_dict: Dict[str, Any] = {
            "dense": embedding,
            "sparse": sparse_vector,
        }

        point_kwargs: Dict[str, Any] = {
            "id": node.node_id,
            "vector": vector_dict,
            "payload": payload,
        }

        # Create Qdrant point
        point = models.PointStruct(**point_kwargs)

        return point

    def add(self, nodes: List[VectorStoreNode]) -> List[str]:
        """
        Add nodes to the Qdrant collection.
        Uses batch processing for sparse embeddings for better performance.

        Args:
            nodes: List of VectorStoreNode objects to add

        Returns:
            List of point IDs that were added
        """
        if not nodes:
            logger.warning("No nodes provided to add")
            return []

        # Generate sparse embeddings in batch for better performance
        texts = [node.text for node in nodes]
        sparse_results = generate_sparse_embeddings_batch(texts)

        # Convert nodes to Qdrant points - fail fast on any error
        points = []
        point_ids = []

        for node, sparse_result in zip(nodes, sparse_results):
            # Let exceptions propagate - fail the entire batch
            point = self._node_to_point_with_sparse(node, sparse_result)
            points.append(point)
            point_ids.append(point.id)

        if not points:
            raise ValueError("No points to add - empty nodes list after processing")

        # Upsert points to Qdrant - fail fast on any error
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            # Get contract_ids for logging (typically all nodes have the same contract_id)
            contract_ids = list(
                set([node.metadata.get("contract_id", "unknown") for node in nodes])
            )
            contract_ids_str = ", ".join(str(cid) for cid in contract_ids)
            logger.info(
                f"Successfully added {len(points)} points to collection {self.collection_name} for contracts: {contract_ids_str}"
            )
        except Exception as e:
            # Include contract info in error logs too
            contract_ids = list(
                set([node.metadata.get("contract_id", "unknown") for node in nodes])
            )
            contract_ids_str = ", ".join(str(cid) for cid in contract_ids)
            logger.error(
                f"Error adding points to Qdrant for contracts {contract_ids_str}: {e}",
                exc_info=True,
            )
            raise

        return point_ids

    def _node_to_point_with_sparse(
        self,
        node: VectorStoreNode,
        sparse_result: Optional[Tuple[List[int], List[float]]],
    ) -> models.PointStruct:
        """
        Convert a VectorStoreNode to a Qdrant point using pre-computed sparse embedding.

        Args:
            node: VectorStoreNode instance
            sparse_result: Pre-computed sparse embedding (indices, values) - optional

        Returns:
            Qdrant PointStruct

        Raises:
            ValueError: If node has no dense embedding
        """
        # Get embedding - ensure it's a list
        embedding = node.embedding
        contract_id = node.metadata.get("contract_id", "unknown")
        if embedding is None:
            raise ValueError(
                f"Contract {contract_id} (node {node.node_id}) has no embedding"
            )

        # Convert embedding to list if it's not already
        if not isinstance(embedding, list):
            embedding = list(embedding)

        # Build payload from node metadata
        payload: Dict[str, Any] = {}

        # Store text content
        payload["text"] = node.text

        # Store all metadata from node
        metadata = node.metadata
        if metadata:
            # Copy metadata to payload
            for key, value in metadata.items():
                # Handle different value types appropriately
                if value is not None:
                    payload[key] = value

        # Store node ID in payload for reference
        payload["node_id"] = node.node_id

        # Build vector dict - always include dense, sparse is optional
        vector_dict: Dict[str, Any] = {
            "dense": embedding,
        }

        # Add sparse vector only if available
        if sparse_result is not None:
            indices, values = sparse_result
            if indices and values:
                sparse_vector = models.SparseVector(indices=indices, values=values)
                vector_dict["sparse"] = sparse_vector
            else:
                logger.warning(
                    f"Empty sparse embedding for contract {contract_id} (node {node.node_id}), skipping sparse vector"
                )
        else:
            logger.warning(
                f"No sparse embedding for contract {contract_id} (node {node.node_id}), storing only dense vector"
            )

        point_kwargs: Dict[str, Any] = {
            "id": node.node_id,
            "vector": vector_dict,
            "payload": payload,
        }

        # Create Qdrant point
        point = models.PointStruct(**point_kwargs)

        return point


def get_qdrant_vector_store() -> CustomQdrantVectorStore:
    """
    Get or create a singleton custom Qdrant vector store.
    Reuses connection across requests for better concurrency.
    Uses CustomQdrantVectorStore instead of LlamaIndex's QdrantVectorStore
    for full control over node storage format.
    """
    global _vector_store

    if _vector_store is None:
        _vector_store = CustomQdrantVectorStore()
        logger.info(
            "Custom vector store initialized (connection reused across requests)"
        )

    return _vector_store
