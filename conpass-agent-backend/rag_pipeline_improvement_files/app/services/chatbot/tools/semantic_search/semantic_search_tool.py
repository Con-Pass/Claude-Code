import asyncio
import os
from typing import Optional, List, Dict, Any, Tuple

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http import models
from llama_index.core.settings import Settings
from llama_index.core.tools import FunctionTool

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.chatbot.tools.semantic_search.sparse_query import (
    generate_sparse_query_embedding,
)
from app.services.chatbot.tools.semantic_search.reranker import rerank_results
from app.services.chatbot.tools.semantic_search.query_expander import rewrite_query

logger = get_logger(__name__)

# ハイブリッド検索チューニングパラメータ（環境変数で設定可能）
QDRANT_TIMEOUT_SECONDS = float(os.getenv("QDRANT_TIMEOUT_SECONDS", "30.0"))
RRF_K = int(os.getenv("RRF_K", "60"))  # チューニング範囲: 20-100
DENSE_PREFETCH_MULTIPLIER = int(os.getenv("DENSE_PREFETCH_MULTIPLIER", "2"))
SPARSE_PREFETCH_MULTIPLIER = int(os.getenv("SPARSE_PREFETCH_MULTIPLIER", "2"))
DENSE_SCORE_THRESHOLD = float(os.getenv("DENSE_SCORE_THRESHOLD", "0.25"))
SPARSE_SCORE_THRESHOLD = float(os.getenv("SPARSE_SCORE_THRESHOLD", "0.0"))
POST_FUSION_THRESHOLD = float(os.getenv("POST_FUSION_THRESHOLD", "0.0"))
MAX_CHUNKS_PER_CONTRACT = int(os.getenv("MAX_CHUNKS_PER_CONTRACT", "3"))
SCORE_THRESHOLD = DENSE_SCORE_THRESHOLD  # 後方互換性


def _build_qdrant_filter(directory_ids: List[int]) -> Optional[Dict[str, Any]]:
    """Create a Qdrant filter that mirrors the old MetadataFilter logic."""
    must: List[Dict[str, Any]] = []
    must_not: List[Dict[str, Any]] = []

    unique_directory_ids = sorted({int(dir_id) for dir_id in directory_ids})
    if unique_directory_ids:
        if len(unique_directory_ids) == 1:
            must.append(
                {
                    "key": "directory_id",
                    "match": {"value": unique_directory_ids[0]},
                }
            )
        else:
            must.append(
                {
                    "key": "directory_id",
                    "match": {"any": unique_directory_ids},
                }
            )

    # Exclude private nodes regardless of whether the value is stored as str/bool.
    must_not.extend(
        [
            {"key": "private", "match": {"value": True}},
        ]
    )

    filter_dict: Dict[str, Any] = {}
    if must:
        filter_dict["must"] = must
    if must_not:
        filter_dict["must_not"] = must_not

    return filter_dict or None


async def _get_query_embedding(query: str) -> List[float]:
    """Generate an embedding for the query using the configured embed model."""
    embed_model = Settings.embed_model
    if embed_model is None:
        raise RuntimeError(
            "Embedding model is not initialized. Call init_model_settings() at startup."
        )

    if hasattr(embed_model, "aget_text_embedding"):
        embedding = await embed_model.aget_text_embedding(query)  # type: ignore[attr-defined]
    else:
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(
            None, embed_model.get_text_embedding, query
        )

    return list(embedding)


def _get_qdrant_client() -> QdrantClient:
    """Get or create a Qdrant client instance with timeout."""
    if not settings.QDRANT_URL or not settings.QDRANT_COLLECTION:
        raise ValueError("QDRANT_URL and QDRANT_COLLECTION must be configured.")

    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        timeout=QDRANT_TIMEOUT_SECONDS,
    )


def _build_qdrant_filter_models(
    directory_ids: List[int],
) -> Optional[models.Filter]:
    """Create a Qdrant Filter model from directory IDs."""
    must: List[models.FieldCondition] = []
    must_not: List[models.FieldCondition] = []

    unique_directory_ids = sorted({int(dir_id) for dir_id in directory_ids})
    if unique_directory_ids:
        if len(unique_directory_ids) == 1:
            must.append(
                models.FieldCondition(
                    key="directory_id",
                    match=models.MatchValue(value=unique_directory_ids[0]),
                )
            )
        else:
            must.append(
                models.FieldCondition(
                    key="directory_id",
                    match=models.MatchAny(any=unique_directory_ids),
                )
            )

    # Exclude private nodes
    must_not.append(
        models.FieldCondition(
            key="private",
            match=models.MatchValue(value=True),
        )
    )

    filter_conditions: List[models.Condition] = []
    if must:
        filter_conditions.extend(must)
    if must_not:
        filter_conditions.extend(must_not)

    if not filter_conditions:
        return None

    return models.Filter(
        must=must if must else None, must_not=must_not if must_not else None
    )


async def _search_qdrant_hybrid(
    dense_embedding: List[float],
    sparse_embedding: Optional[Tuple[List[int], List[float]]],
    directory_ids: List[int],
    top_k: int,
) -> List[Dict[str, Any]]:
    """
    Execute hybrid search using Qdrant's Universal Query API with RRF fusion.
    Combines dense (semantic) and sparse (BM25 keyword) search results.
    """
    if not settings.QDRANT_URL or not settings.QDRANT_COLLECTION:
        raise ValueError("QDRANT_URL and QDRANT_COLLECTION must be configured.")

    client = _get_qdrant_client()
    collection_name = settings.QDRANT_COLLECTION

    # Build filter
    q_filter = _build_qdrant_filter_models(directory_ids)

    # Prefetch queries for both dense and sparse vectors
    prefetch_queries: List[models.Prefetch] = []

    # Dense vector prefetch (named "dense" vector from collection config)
    prefetch_queries.append(
        models.Prefetch(
            query=dense_embedding,
            using="dense",  # Named dense vector matching collection config
            limit=max(1, top_k * DENSE_PREFETCH_MULTIPLIER),
            score_threshold=DENSE_SCORE_THRESHOLD,
            filter=q_filter,
        )
    )

    # Sparse vector prefetch (if available)
    if sparse_embedding is not None:
        indices, values = sparse_embedding
        sparse_vector = models.SparseVector(indices=indices, values=values)
        sparse_prefetch_kwargs = {
            "query": sparse_vector,
            "using": "sparse",
            "limit": max(1, top_k * SPARSE_PREFETCH_MULTIPLIER),
            "filter": q_filter,
        }
        if SPARSE_SCORE_THRESHOLD > 0:
            sparse_prefetch_kwargs["score_threshold"] = SPARSE_SCORE_THRESHOLD
        prefetch_queries.append(models.Prefetch(**sparse_prefetch_kwargs))
    else:
        logger.warning(
            "Sparse embedding is None - hybrid search will use dense-only. "
            "This may indicate an issue with sparse model initialization."
        )

    # Execute hybrid search with RRF fusion
    try:
        response = client.query_points(
            collection_name=collection_name,
            prefetch=prefetch_queries,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=max(1, top_k),
            with_payload=True,
            with_vectors=False,
            search_params=models.SearchParams(exact=True),
        )

        # Convert ScoredPoint objects to dict format for compatibility
        points: List[Dict[str, Any]] = []
        for point in response.points:
            points.append(
                {
                    "id": point.id,
                    "score": point.score,
                    "payload": point.payload or {},
                }
            )

        # Sort by score descending, then by ID ascending for deterministic ordering
        # This prevents non-deterministic results when RRF fusion produces tied scores
        points.sort(key=lambda p: (-p["score"], str(p["id"])))

        # Log statistics about contract_id distribution
        contract_ids = [
            p.get("payload", {}).get("contract_id")
            for p in points
            if p.get("payload", {}).get("contract_id") is not None
        ]
        unique_contracts = len(set(contract_ids))
        logger.info(
            f"Hybrid search returned {len(points)} results from {unique_contracts} unique contracts"
        )

        return points

    except Exception as e:
        logger.error(f"Error in hybrid search: {e}", exc_info=True)
        # Fallback to dense-only search if hybrid fails
        logger.warning("Falling back to dense-only search")
        return await _search_qdrant_dense_fallback(
            dense_embedding, directory_ids, top_k
        )


async def _search_qdrant_dense_fallback(
    embedding: List[float],
    directory_ids: List[int],
    top_k: int,
) -> List[Dict[str, Any]]:
    """Fallback to dense-only search if hybrid search fails."""
    if not settings.QDRANT_URL or not settings.QDRANT_COLLECTION:
        raise ValueError("QDRANT_URL and QDRANT_COLLECTION must be configured.")

    endpoint = (
        f"{settings.QDRANT_URL}/collections/{settings.QDRANT_COLLECTION}/points/query"
    )
    headers = {"Content-Type": "application/json"}
    if settings.QDRANT_API_KEY:
        headers["api-key"] = settings.QDRANT_API_KEY

    body: Dict[str, Any] = {
        "query": embedding,
        "limit": max(1, top_k),
        "score_threshold": SCORE_THRESHOLD,
        "with_payload": True,
        "with_vector": False,
    }

    q_filter = _build_qdrant_filter(directory_ids)
    if q_filter:
        body["filter"] = q_filter

    async with httpx.AsyncClient(timeout=QDRANT_TIMEOUT_SECONDS) as client:
        response = await client.post(endpoint, json=body, headers=headers)
        response.raise_for_status()

    data = response.json()
    logger.info(f"Qdrant fallback response: {data}")
    result = data.get("result", {})
    points = result.get("points", [])

    # Sort by score descending, then by ID ascending for deterministic ordering
    points.sort(key=lambda p: (-p.get("score", 0.0), str(p.get("id", ""))))

    # Log statistics about contract_id distribution
    contract_ids = [
        p.get("payload", {}).get("contract_id")
        for p in points
        if p.get("payload", {}).get("contract_id") is not None
    ]
    unique_contracts = len(set(contract_ids))
    logger.info(
        f"Dense fallback search returned {len(points)} results from {unique_contracts} unique contracts"
    )

    return points


def _format_sources(
    points: List[Dict[str, Any]],
    deduplicate_by_contract: bool = True,
    max_chunks_per_contract: int = 1,
) -> List[Dict[str, Any]]:
    """
    Convert Qdrant points into the tool's expected response structure.

    Args:
        points: List of Qdrant search results
        deduplicate_by_contract: If True, limit chunks per contract_id.
        max_chunks_per_contract: Maximum chunks to keep per contract (default 1 for backward compat).
    """
    logger.info(f"_format_sources: Processing {len(points)} points")

    if deduplicate_by_contract:
        # contract_idごとにチャンクをグループ化し、上位N件を保持
        from collections import defaultdict

        contract_chunks: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)

        for original_idx, point in enumerate(points):
            payload = (point.get("payload") or {}).copy()
            contract_id = payload.get("contract_id")
            contract_chunks[contract_id].append({
                "point": point,
                "score": point.get("score", 0.0),
                "original_idx": original_idx,
            })

        # 各契約から上位max_chunks_per_contractチャンクを選択
        selected = []
        for contract_id, chunks in contract_chunks.items():
            chunks.sort(key=lambda x: (-x["score"], x["original_idx"]))
            selected.extend(chunks[:max_chunks_per_contract])

        # 全体をスコア順にソート
        selected.sort(key=lambda x: (-x["score"], x["original_idx"]))

        logger.info(
            f"_format_sources: {len(contract_chunks)} unique contracts, "
            f"{len(selected)} chunks selected (max {max_chunks_per_contract}/contract, "
            f"from {len(points)} total)"
        )

        points_to_format = [entry["point"] for entry in selected]
    else:
        points_to_format = points

    # Apply score thresholding after deduplication / selection
    before_threshold_count = len(points_to_format)
    effective_threshold = POST_FUSION_THRESHOLD if POST_FUSION_THRESHOLD > 0 else SCORE_THRESHOLD
    points_to_format = [
        p for p in points_to_format if p.get("score", 0.0) >= effective_threshold
    ]
    logger.info(
        f"_format_sources: After score threshold ({effective_threshold}), "
        f"{len(points_to_format)} points remain (from {before_threshold_count})"
    )

    sources: List[Dict[str, Any]] = []
    for idx, point in enumerate(points_to_format, start=1):
        payload = point.get("payload") or {}
        metadata = dict(payload)

        source_text = metadata.pop("text", "")
        contract_id = metadata.get("contract_id")

        # Strip internal metadata fields not meant for agents.
        metadata.pop("private", None)
        metadata.pop("directory_id", None)
        metadata.pop("summary", None)

        contract_url = (
            f"{settings.CONPASS_FRONTEND_BASE_URL}/contract/{contract_id}"
            if contract_id is not None
            else None
        )

        source_entry = {
            "source_number": idx,
            "contract_id": contract_id,
            "contract_url": contract_url,
            "metadata": metadata,
            "excerpt": source_text,
            "score": point.get("score", 0.0),
        }

        # 構造メタデータがあれば含める
        article_number = metadata.get("article_number")
        section_title = metadata.get("section_title")
        if article_number is not None:
            source_entry["article_number"] = article_number
        if section_title:
            source_entry["section_title"] = section_title

        sources.append(source_entry)

    return sources


async def semantic_search(
    directory_ids: List[int],
    query: str,
    *,
    similarity_top_k: Optional[int] = None,
    deduplicate_by_contract: bool = True,
) -> List[Dict[str, Any]]:
    """
    Query the index using hybrid search (dense + sparse BM25).
    Combines semantic similarity with keyword matching for better results.

    Args:
        directory_ids: List of directory IDs to filter by
        query: The search query text
        similarity_top_k: Number of results to return from Qdrant (before deduplication)
        deduplicate_by_contract: If True, keep only highest-scoring chunk per contract_id
    """
    logger.info(f"semantic_search_tool called with query: {query}")
    try:
        # クエリ拡張: Dense用とSparse用に分離
        dense_query, sparse_query = await rewrite_query(query)

        # Generate both dense and sparse embeddings for hybrid search
        dense_embedding = await _get_query_embedding(dense_query)

        # Generate sparse embedding using BM25 (same model as ingestion)
        # Run in executor since FastEmbed may be blocking
        loop = asyncio.get_running_loop()
        sparse_embedding = await loop.run_in_executor(
            None, generate_sparse_query_embedding, sparse_query
        )

        top_k = similarity_top_k or settings.TOP_K

        # Execute hybrid search with RRF fusion
        points = await _search_qdrant_hybrid(
            dense_embedding, sparse_embedding, directory_ids, top_k
        )

        # クロスエンコーダリランキング（有効化時のみ）
        points = await rerank_results(query, points)

        return _format_sources(
            points,
            deduplicate_by_contract=deduplicate_by_contract,
            max_chunks_per_contract=MAX_CHUNKS_PER_CONTRACT,
        )

    except httpx.HTTPStatusError as exc:
        logger.exception(
            "Qdrant HTTP error %s while querying index: %s",
            exc.response.status_code if exc.response else "unknown",
            exc.response.text if exc.response else "no body",
        )
    except Exception as e:
        logger.exception(f"Error in semantic_search: {e}")

    return [
        {
            "error": "An unexpected error occurred while querying the index",
        }
    ]


def get_semantic_search_tool(
    directory_ids: List[int],
    name: Optional[str] = None,
    description: Optional[str] = None,
    **kwargs,
) -> FunctionTool:
    """
    Get a semantic search tool for the given index.

    Args:
        directory_ids: List of directory IDs to search within.
        name (optional): The name of the tool.
        description (optional): The description of the tool.
    """
    if name is None:
        name = "semantic_search"
    if description is None:
        description = """
        Search ACROSS many contracts to discover WHICH contracts contain specific content/clauses/text using hybrid RAG (dense + sparse BM25).

        Use this tool when
        - The user wants to discover WHICH contracts mention/contain certain content (clauses, obligations, definitions, thresholds, etc.)
        - The user wants to list/find contracts that mention terms, people, legal concepts, or other text not stored in metadata
        - The user asks for contracts similar to an UPLOADED FILE: first call get_file_content_tool to retrieve the file content, then call semantic_search with that content (or a summary if the file is very long) as the query parameter
        - Searching across MULTIPLE contracts to find relevant ones
        - Keywords: "which contracts mention", "find contracts that have", "contracts with clauses about", "contracts similar to this file", "list contracts like this uploaded file"

        Do NOT use this tool when
        - The user specifies a CONTRACT ID and wants details FROM that specific contract → use read_contracts_tool instead
        - The request can be satisfied with metadata only (company names, dates, contract type, auto-renewal, court) → use metadata_search instead

        Critical routing examples
        - "Which contracts have SLA terms?" → semantic_search ✓ (discover across many)
        - "What are the SLA terms in contract 4824?" → read_contracts_tool ✓ (specific contract ID)
        - "Find contracts with ABC Corp" → metadata_search ✓ (metadata only)
        - "List contracts similar to this uploaded file" → first get_file_content_tool, then semantic_search(query=retrieved file content or summary) ✓

        Call guidance
        - query: Use the user's exact question as the query parameter. Only modify or add context when: (1) the user explicitly references previous results (e.g., "those contracts", "the previous search"), (2) minimal context is absolutely necessary to understand what the user is asking (e.g., if user says "that contract" without context), or (3) the question is incomplete and cannot be understood without conversation history. Do NOT rephrase or "improve" the user's wording unless context is needed.
        - Use returned sources to ground answers and cite contract_id/contract_url.

        Returns
        - List of sources with: source_number, contract_id, contract_url, metadata, excerpt.
        
        CRITICAL - URL Handling
        - Each source includes a "contract_url" field with the valid URL to view that contract
        - NEVER fabricate or make up URLs - ONLY use the URLs provided in the tool response
        - If displaying contracts or sources, always include the URL from the response data
        """

    # Create a wrapper function that includes directory_ids
    async def semantic_search_with_dirs(query: str) -> List[Dict[str, Any]]:
        return await semantic_search(directory_ids, query, **kwargs)

    return FunctionTool.from_defaults(
        async_fn=semantic_search_with_dirs,
        name=name,
        description=description,
    )
