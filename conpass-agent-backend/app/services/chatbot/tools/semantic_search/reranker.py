"""
クロスエンコーダリランキングモジュール。

ハイブリッド検索後の結果をクロスエンコーダモデルでリスコアリングし、
検索品質を向上させる。

サポートするリランカー:
- Cohere rerank-multilingual-v3.0（API型、日本語対応）
"""

import os
from typing import Any, Dict, List, Optional

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# リランカー設定
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "false").lower() == "true"
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "rerank-multilingual-v3.0")
RERANKER_TOP_N = int(os.getenv("RERANKER_TOP_N", "20"))
RERANKER_THRESHOLD = float(os.getenv("RERANKER_THRESHOLD", "0.1"))
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")


async def rerank_results(
    query: str,
    points: List[Dict[str, Any]],
    top_n: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    クロスエンコーダでリランキングする。

    Args:
        query: 検索クエリ
        points: Qdrantからの検索結果（各要素にpayload.textを含む）
        top_n: リランキング後の上位N件（Noneの場合はRERANKER_TOP_N）

    Returns:
        リランクスコアでソートされたpoints（reranker_scoreフィールドを追加）
    """
    if not RERANKER_ENABLED:
        return points

    if not points:
        return points

    if not COHERE_API_KEY:
        logger.warning("COHERE_API_KEY not set, skipping reranking")
        return points

    top_n = top_n or RERANKER_TOP_N

    try:
        import cohere

        co = cohere.AsyncClientV2(api_key=COHERE_API_KEY)

        # テキストを抽出
        documents = []
        for point in points:
            text = (point.get("payload") or {}).get("text", "")
            documents.append(text)

        # リランキング実行
        response = await co.rerank(
            model=RERANKER_MODEL,
            query=query,
            documents=documents,
            top_n=min(top_n, len(documents)),
        )

        # リランクスコアでソートされた結果を構築
        reranked_points = []
        for result in response.results:
            idx = result.index
            point = points[idx].copy()
            point["reranker_score"] = result.relevance_score
            # 元のRRFスコアを保持
            point["rrf_score"] = point.get("score", 0.0)
            # リランカースコアをプライマリスコアに
            point["score"] = result.relevance_score
            reranked_points.append(point)

        # 閾値フィルタ
        before_filter = len(reranked_points)
        reranked_points = [
            p for p in reranked_points
            if p.get("reranker_score", 0.0) >= RERANKER_THRESHOLD
        ]

        logger.info(
            f"Reranking: {len(points)} -> {before_filter} (top_n) -> "
            f"{len(reranked_points)} (threshold={RERANKER_THRESHOLD})"
        )

        return reranked_points

    except ImportError:
        logger.warning("cohere package not installed, skipping reranking")
        return points
    except Exception as e:
        logger.error(f"Reranking failed, returning original results: {e}")
        return points
