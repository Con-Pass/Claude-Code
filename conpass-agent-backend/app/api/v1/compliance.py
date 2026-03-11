"""
コンプライアンスAPI エンドポイント

契約のコンプライアンススコア算出とアカウント全体のサマリーを提供する。
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.logging_config import get_logger
from app.services.compliance.compliance_score_service import ComplianceScoreService

logger = get_logger(__name__)

compliance_router = APIRouter()

_compliance_service: Optional[ComplianceScoreService] = None


def _get_service() -> ComplianceScoreService:
    global _compliance_service
    if _compliance_service is None:
        _compliance_service = ComplianceScoreService()
    return _compliance_service


class ScoreRequest(BaseModel):
    contract_id: str = Field(..., description="契約ID")
    contract_body: str = Field(..., description="契約書本文")


class ScoreResponse(BaseModel):
    contract_id: str
    score: int = Field(..., ge=0, le=100, description="コンプライアンススコア (0-100)")
    issues: list = Field(default_factory=list, description="法令適合性の問題リスト")


class SummaryResponse(BaseModel):
    account_id: str
    total_contracts: int
    average_score: float
    score_distribution: dict
    contracts_requiring_attention: list


@compliance_router.post(
    "/score",
    response_model=ScoreResponse,
    summary="コンプライアンススコア算出",
    description="契約1件のコンプライアンススコアを算出する (0-100)",
)
async def calculate_compliance_score(request: ScoreRequest):
    """
    契約書のコンプライアンススコアを算出する。

    スコア算出ロジック:
    - 基準点: 100点
    - HIGH issue: -20点
    - MEDIUM issue: -10点
    - LOW issue: -5点
    """
    try:
        service = _get_service()
        result = await service.calculate_score(
            contract_id=request.contract_id,
            contract_body=request.contract_body,
        )
        return ScoreResponse(
            contract_id=result["contract_id"],
            score=result["score"],
            issues=result["issues"],
        )
    except Exception as e:
        logger.exception(f"Error calculating compliance score: {e}")
        raise HTTPException(
            status_code=500,
            detail="コンプライアンススコアの算出に失敗しました",
        )


@compliance_router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="コンプライアンスサマリー",
    description="アカウント全体のコンプライアンス状況を集計する",
)
async def get_compliance_summary(
    account_id: str = Query(..., description="アカウントID"),
):
    """
    アカウント全体のコンプライアンス状況を集計する。

    レスポンス:
    - total_contracts: 契約総数
    - average_score: 平均スコア
    - score_distribution: スコア分布 (high: 80+, medium: 60-79, low: 40-59, critical: <40)
    - contracts_requiring_attention: スコア60以下の契約リスト
    """
    try:
        service = _get_service()
        # NOTE: 本番環境では、account_idに紐づく全契約のスコアをDBから取得する。
        # プロトタイプ段階ではスコアキャッシュ未実装のため空リストで返す。
        result = await service.get_account_summary(
            account_id=account_id,
            scores=[],  # TODO: Firestoreからキャッシュされたスコアを取得
        )
        return SummaryResponse(**result)
    except Exception as e:
        logger.exception(f"Error getting compliance summary: {e}")
        raise HTTPException(
            status_code=500,
            detail="コンプライアンスサマリーの取得に失敗しました",
        )
