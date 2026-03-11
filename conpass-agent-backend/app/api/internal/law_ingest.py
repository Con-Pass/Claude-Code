"""
法令インジェスト 内部エンドポイント

Django バックエンドからのみ呼び出される内部 API。
JWTAuthMiddleware はこのパス(/api/internal/*)をスキップする。
"""
import re
import uuid
import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
    SparseVector,
    VectorParams,
    Distance,
    SparseVectorParams,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
)

from app.core.config import settings
from app.core.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)

# 段落区切りパターン（空行・改行2つ以上）
_PARAGRAPH_SEP = re.compile(r'\n{2,}|\r\n\r\n')


class LawIngestRequest(BaseModel):
    law_id: int
    law_name: str
    law_short_name: str = ""
    law_number: str = ""
    effective_date: Optional[str] = None
    text: str


def _get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=60)


def _ensure_laws_collection(client: QdrantClient, collection_name: str) -> None:
    """conpass_laws コレクションが存在しなければ作成する"""
    try:
        client.get_collection(collection_name)
        logger.info(f"コレクション {collection_name} は既存")
        return
    except Exception:
        pass

    client.create_collection(
        collection_name=collection_name,
        vectors_config={"dense": VectorParams(size=384, distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams()},
    )
    for field, schema in [
        ("law_id",         PayloadSchemaType.INTEGER),
        ("law_name",       PayloadSchemaType.TEXT),     # MatchText による部分一致検索のため TEXT
        ("law_short_name", PayloadSchemaType.TEXT),     # MatchText による部分一致検索のため TEXT
        ("article_number", PayloadSchemaType.KEYWORD),
    ]:
        client.create_payload_index(collection_name, field, schema)
    logger.info(f"コレクション {collection_name} を作成しました")


def _chunk_by_article(text: str, max_chars: int = 1500) -> list[str]:
    """段落単位で結合しながら max_chars 以内に収めるチャンク分割。
    正規表現で条文参照に誤反応しないよう、空行（段落区切り）ベースで処理する。
    """
    paragraphs = [p.strip() for p in _PARAGRAPH_SEP.split(text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # para が単体で max_chars を超える場合は固定長で分割
        if len(para) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(para), max_chars - 100):
                chunks.append(para[i:i + max_chars])
            continue

        # 結合しても max_chars 以内なら続ける
        sep = "\n\n" if current else ""
        if len(current) + len(sep) + len(para) <= max_chars:
            current = current + sep + para
        else:
            if current:
                chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    return chunks or [text[:max_chars]]


def _extract_article_number(chunk: str) -> str:
    m = re.match(
        r'(第[\d一二三四五六七八九十百千万]+条(?:の[\d一二三四五六七八九十百千万]+)?|Article\s+\d+)',
        chunk,
    )
    return m.group(1) if m else ""


@router.post("/ingest")
async def ingest_law(req: LawIngestRequest):
    """法令テキストをチャンク化して Qdrant conpass_laws コレクションへ格納する"""
    from llama_index.core.settings import Settings as LlamaSettings
    from app.services.chatbot.tools.semantic_search.sparse_query import get_sparse_embedding_model

    laws_collection = settings.QDRANT_LAWS_COLLECTION
    client = _get_qdrant_client()

    _ensure_laws_collection(client, laws_collection)

    # 既存ポイントを削除（再インデックス対応）
    try:
        client.delete(
            collection_name=laws_collection,
            points_selector=Filter(must=[
                FieldCondition(key="law_id", match=MatchValue(value=req.law_id))
            ]),
        )
    except Exception:
        pass

    embed_model  = LlamaSettings.embed_model
    sparse_model = get_sparse_embedding_model()

    chunks = _chunk_by_article(req.text)
    article_numbers = [_extract_article_number(chunk) for chunk in chunks]

    logger.info(f"[LawIngest] law_id={req.law_id}: {len(chunks)} チャンクのエンベディングを一括生成中...")

    # Dense embedding をバッチで一括生成（逐次処理より大幅に高速）
    import asyncio
    loop = asyncio.get_running_loop()
    dense_vecs = await loop.run_in_executor(
        None, embed_model.get_text_embedding_batch, chunks
    )

    # Sparse embedding をバッチで一括生成
    sparse_embs = list(sparse_model.embed(chunks))

    logger.info(f"[LawIngest] law_id={req.law_id}: エンベディング生成完了、ポイント構築中...")

    points = []
    for i, (chunk, article_number, dense_vec, sparse_emb) in enumerate(
        zip(chunks, article_numbers, dense_vecs, sparse_embs)
    ):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"law_{req.law_id}_{i}"))
        points.append(PointStruct(
            id=point_id,
            vector={
                "dense": list(dense_vec),
                "sparse": SparseVector(
                    indices=[int(x) for x in sparse_emb.indices],
                    values=[float(x) for x in sparse_emb.values],
                ),
            },
            payload={
                "law_id":         req.law_id,
                "law_name":       req.law_name,
                "law_short_name": req.law_short_name,
                "law_number":     req.law_number,
                "effective_date": req.effective_date,
                "article_number": article_number,
                "chunk_index":    i,
                "text":           chunk,
            },
        ))

    # Qdrant の 1 リクエストあたりのペイロード上限 (32MB) を超えないようにバッチ処理
    UPSERT_BATCH_SIZE = 50
    for batch_start in range(0, len(points), UPSERT_BATCH_SIZE):
        batch = points[batch_start:batch_start + UPSERT_BATCH_SIZE]
        client.upsert(collection_name=laws_collection, points=batch)
        logger.info(
            f"[LawIngest] upsert バッチ {batch_start // UPSERT_BATCH_SIZE + 1}: "
            f"{len(batch)} 件 (合計 {min(batch_start + UPSERT_BATCH_SIZE, len(points))}/{len(points)})"
        )

    logger.info(f"[LawIngest] law_id={req.law_id} ({req.law_name}): {len(points)} 条文をインデックス化")
    return {"articles_indexed": len(points)}


@router.delete("/{law_id}")
async def delete_law(law_id: int):
    """指定した法令の全ポイントを Qdrant から削除する"""
    laws_collection = settings.QDRANT_LAWS_COLLECTION
    client = _get_qdrant_client()
    try:
        client.delete(
            collection_name=laws_collection,
            points_selector=Filter(must=[
                FieldCondition(key="law_id", match=MatchValue(value=law_id))
            ]),
        )
    except Exception as e:
        logger.warning(f"[LawDelete] law_id={law_id}: {e}")
    return {"deleted": True}
