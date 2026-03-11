"""
Sparse embedding utilities for hybrid search queries.
BGE-M3 の SPLADE スタイル sparse vector を使用する。

旧実装 (Qdrant/bm25) と異なり、BGE-M3 の sparse は多言語対応済み。
日本語・英語・中国語等の固有名詞や専門用語を正しくトークン化できる。
"""

from typing import Optional, Tuple, List

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def get_sparse_embedding_model():
    """
    BGE-M3 シングルトンを返す（sparse_query の後方互換インターフェース）。
    model_settings.py の init_model_settings() でウォームアップ済み。
    """
    from app.services.bge_m3 import get_bge_m3_model
    return get_bge_m3_model()


def generate_sparse_query_embedding(
    query: str,
) -> Optional[Tuple[List[int], List[float]]]:
    """
    BGE-M3 の SPLADE sparse ベクトルをクエリから生成する。

    Args:
        query: 検索クエリ（日本語・英語・その他多言語）

    Returns:
        (indices, values) タプル。indices は BGE-M3 tokenizer の vocab ID。
        空の場合は None。
    """
    if not query or not query.strip():
        return None

    try:
        from app.services.bge_m3 import encode_single_sparse
        indices, values = encode_single_sparse(query)
        if not indices:
            return None
        logger.debug(f"Sparse embedding: {len(indices)} non-zero tokens for query")
        return (indices, values)

    except Exception as e:
        logger.error(f"Error generating sparse query embedding: {e}", exc_info=True)
        return None
