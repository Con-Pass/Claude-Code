"""
低信頼度メタデータのレビューキューAPI
confidence_score < threshold のデータをユーザーレビュー待ちにする
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

METADATA_CONFIDENCE_THRESHOLD = float(
    os.getenv("METADATA_CONFIDENCE_THRESHOLD", "0.7")
)


class ReviewQueueItem(BaseModel):
    """レビュー待ちメタデータの項目"""

    point_id: str = Field(..., description="QdrantポイントID")
    contract_id: Optional[int] = Field(None, description="契約書ID")
    confidence_score: float = Field(..., description="信頼度スコア (0.0-1.0)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="メタデータ")
    text_excerpt: str = Field(default="", description="テキスト抜粋")


class ReviewQueueResponse(BaseModel):
    """レビューキューのレスポンス"""

    items: List[ReviewQueueItem] = Field(default_factory=list)
    total: int = Field(0, description="合計件数")
    threshold: float = Field(..., description="適用された閾値")


class ApproveMetadataRequest(BaseModel):
    """メタデータ承認リクエスト"""

    corrected_metadata: Dict[str, Any] = Field(
        ..., description="修正後のメタデータ"
    )


class ApproveMetadataResponse(BaseModel):
    """メタデータ承認レスポンス"""

    status: str = Field(..., description="処理結果")
    message: str = Field(..., description="メッセージ")
    contract_id: Optional[int] = Field(None, description="契約書ID")


@router.get(
    "/review-queue",
    summary="低信頼度メタデータ一覧取得",
    description="信頼度スコアが閾値未満のメタデータ一覧を返却",
    response_model=ReviewQueueResponse,
    tags=["metadata-crud"],
)
async def get_review_queue(
    request: Request,
    account_id: str,
    threshold: float = METADATA_CONFIDENCE_THRESHOLD,
    limit: int = 50,
):
    """
    信頼度スコアの低いメタデータ一覧を返却。

    Qdrantでconfidence_score < threshold のペイロードをフィルタし、
    ユーザーレビュー待ちの項目をリストとして返す。

    Args:
        request: FastAPIリクエスト
        account_id: アカウントID
        threshold: 信頼度閾値（デフォルト: 0.7）
        limit: 返却件数上限（デフォルト: 50）
    """
    logger.info(
        f"[REVIEW_QUEUE] Fetching review queue for account={account_id}, "
        f"threshold={threshold}, limit={limit}"
    )

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models

        if not settings.QDRANT_URL or not settings.QDRANT_COLLECTION:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Qdrant is not configured",
            )

        client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=10.0,
        )

        # confidence_score < threshold のポイントをフィルタ
        scroll_result = client.scroll(
            collection_name=settings.QDRANT_COLLECTION,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="confidence_score",
                        range=models.Range(lt=threshold),
                    ),
                ]
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        points, _ = scroll_result

        items = []
        for point in points:
            payload = point.payload or {}
            items.append(
                ReviewQueueItem(
                    point_id=str(point.id),
                    contract_id=payload.get("contract_id"),
                    confidence_score=payload.get("confidence_score", 0.0),
                    metadata={
                        k: v
                        for k, v in payload.items()
                        if k not in ("text", "confidence_score", "private")
                    },
                    text_excerpt=(payload.get("text", ""))[:200],
                )
            )

        logger.info(
            f"[REVIEW_QUEUE] Found {len(items)} items below threshold {threshold}"
        )

        return ReviewQueueResponse(
            items=items,
            total=len(items),
            threshold=threshold,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[REVIEW_QUEUE] Error fetching review queue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch review queue",
        )


@router.post(
    "/review-queue/{contract_id}/approve",
    summary="メタデータ承認",
    description="ユーザーが確認・修正したデータを承認してQdrantを更新",
    response_model=ApproveMetadataResponse,
    tags=["metadata-crud"],
)
async def approve_metadata(
    request: Request,
    contract_id: int,
    body: ApproveMetadataRequest,
):
    """
    ユーザーが確認・修正したデータを承認してQdrantを更新。

    指定された契約IDに紐づくQdrantポイントのメタデータペイロードを
    修正後の値で更新し、confidence_scoreを1.0に設定する。

    Args:
        request: FastAPIリクエスト
        contract_id: 契約書ID
        body: 修正後のメタデータ
    """
    logger.info(
        f"[REVIEW_QUEUE] Approving metadata for contract_id={contract_id}"
    )

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models

        if not settings.QDRANT_URL or not settings.QDRANT_COLLECTION:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Qdrant is not configured",
            )

        client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=10.0,
        )

        # contract_idに紐づくポイントを取得
        scroll_result = client.scroll(
            collection_name=settings.QDRANT_COLLECTION,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="contract_id",
                        match=models.MatchValue(value=contract_id),
                    ),
                ]
            ),
            limit=100,
            with_payload=True,
            with_vectors=False,
        )

        points, _ = scroll_result

        if not points:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No points found for contract_id={contract_id}",
            )

        # 各ポイントのペイロードを更新
        point_ids = [point.id for point in points]
        update_payload = {
            **body.corrected_metadata,
            "confidence_score": 1.0,  # 承認済みなので最大値
            "reviewed": True,
        }

        client.set_payload(
            collection_name=settings.QDRANT_COLLECTION,
            payload=update_payload,
            points=point_ids,
        )

        logger.info(
            f"[REVIEW_QUEUE] Updated {len(point_ids)} points for contract_id={contract_id}"
        )

        return ApproveMetadataResponse(
            status="success",
            message=f"Updated {len(point_ids)} point(s) for contract {contract_id}",
            contract_id=contract_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[REVIEW_QUEUE] Error approving metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve metadata",
        )
