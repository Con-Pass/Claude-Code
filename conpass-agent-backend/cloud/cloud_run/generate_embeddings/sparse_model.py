import logging
from typing import Optional, List, Tuple
from fastembed import SparseTextEmbedding

logger = logging.getLogger(__name__)

# Singleton instance for model reuse
_sparse_embedding_model: Optional[SparseTextEmbedding] = None


def get_sparse_embedding_model() -> SparseTextEmbedding:
    """
    Get or create a singleton sparse embedding model (BM25-style).
    Reuses model instance across requests for better performance.

    Uses FastEmbed's SparseTextEmbedding with Qdrant's recommended BM25 model
    for production-ready hybrid search.
    """
    global _sparse_embedding_model

    if _sparse_embedding_model is None:
        # Use Qdrant's recommended BM25 model for sparse embeddings
        # This provides proper IDF weighting and length normalization
        model_name = "Qdrant/bm25"

        try:
            _sparse_embedding_model = SparseTextEmbedding(model_name=model_name)
            logger.info(f"Sparse embedding model initialized: {model_name}")
        except Exception as e:
            logger.error(
                f"Failed to initialize sparse embedding model {model_name}: {e}",
                exc_info=True,
            )
            raise

    return _sparse_embedding_model


def generate_sparse_embedding(text: str) -> Optional[Tuple[List[int], List[float]]]:
    """
    Generate a sparse embedding (BM25-style) for the given text.

    Args:
        text: Input text to embed

    Returns:
        Tuple of (indices, values) for the sparse vector, or None if empty
    """
    if not text or not text.strip():
        return None

    try:
        model = get_sparse_embedding_model()

        # FastEmbed's SparseTextEmbedding.embed returns an iterator
        # Each item is a SparseEmbedding object with indices and values
        embeddings = list(model.embed([text]))

        if not embeddings:
            return None

        # Get the first (and only) sparse embedding
        sparse_embedding = embeddings[0]

        # SparseEmbedding has indices and values attributes
        # Convert to lists for Qdrant's SparseVector model
        indices = [int(idx) for idx in sparse_embedding.indices]
        values = [float(val) for val in sparse_embedding.values]

        if not indices:
            return None

        return (indices, values)

    except Exception as e:
        logger.error(f"Error generating sparse embedding: {e}", exc_info=True)
        return None


def generate_sparse_embeddings_batch(
    texts: List[str],
) -> List[Optional[Tuple[List[int], List[float]]]]:
    """
    Generate sparse embeddings (BM25-style) for a batch of texts.
    More efficient than calling generate_sparse_embedding() multiple times.

    Args:
        texts: List of input texts to embed

    Returns:
        List of tuples (indices, values) for each text, or None for empty/invalid texts
    """
    if not texts:
        return []

    # Filter out empty texts and track their positions
    valid_texts = []
    valid_indices = []
    for i, text in enumerate(texts):
        if text and text.strip():
            valid_texts.append(text)
            valid_indices.append(i)

    if not valid_texts:
        return [None] * len(texts)

    try:
        model = get_sparse_embedding_model()

        # FastEmbed's SparseTextEmbedding.embed returns an iterator
        # Process all texts in batch
        embeddings = list(model.embed(valid_texts))

        # Create result list with None for empty texts
        results: List[Optional[Tuple[List[int], List[float]]]] = [None] * len(texts)

        # Fill in results for valid texts
        for idx, sparse_embedding in zip(valid_indices, embeddings):
            indices = [int(i) for i in sparse_embedding.indices]
            values = [float(v) for v in sparse_embedding.values]

            if indices:
                results[idx] = (indices, values)

        return results

    except Exception as e:
        logger.warning(
            f"Error generating sparse embeddings batch: {e}. Returning None for all texts.",
            exc_info=True,
        )
        return [None] * len(texts)  # Return None for all instead of failing
