"""
ベンチマークDB API エンドポイント
業界・契約種別ごとの統計と、個別契約の比較を提供する
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.logging_config import get_logger
from app.services.benchmark.benchmark_service import BenchmarkService

logger = get_logger(__name__)

benchmark_router = APIRouter()

_benchmark_service: Optional[BenchmarkService] = None


def _get_service() -> BenchmarkService:
    global _benchmark_service
    if _benchmark_service is None:
        _benchmark_service = BenchmarkService()
    return _benchmark_service


@benchmark_router.get(
    "/stats",
    summary="ベンチマーク統計取得",
    description="業界・契約種別ごとの匿名化統計（契約期間分布・支払条件割合・損害賠償上限分布・自動更新条項割合）を返す",
)
async def get_benchmark_stats(
    industry: Optional[str] = Query(None, description="業界フィルタ（例: 建設業, IT, 不動産）"),
    contract_type: Optional[str] = Query(None, description="契約種別フィルタ（例: 請負契約, 賃貸借契約）"),
):
    try:
        service = _get_service()
        result = await service.get_stats(industry=industry, contract_type=contract_type)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.exception(f"Benchmark stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@benchmark_router.get(
    "/compare",
    summary="契約ベンチマーク比較",
    description="指定契約を業界平均と比較し、乖離度を返す",
)
async def compare_contract(
    contract_id: str = Query(..., description="比較対象の契約ID"),
):
    try:
        service = _get_service()
        result = await service.compare_contract(contract_id=contract_id)
        if result.get("error"):
            raise HTTPException(status_code=404, detail=result["error"])
        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Benchmark compare error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
