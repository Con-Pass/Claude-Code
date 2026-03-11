"""
ベンチマーク参照ツール
契約データの業界平均比較・統計をエージェントから利用可能にする
"""
from typing import Any, Dict, Optional

from llama_index.core.tools import FunctionTool

from app.core.logging_config import get_logger
from app.services.benchmark.benchmark_service import BenchmarkService

logger = get_logger(__name__)

_benchmark_service: Optional[BenchmarkService] = None


def _get_service() -> BenchmarkService:
    global _benchmark_service
    if _benchmark_service is None:
        _benchmark_service = BenchmarkService()
    return _benchmark_service


async def benchmark_stats(
    industry: Optional[str] = None,
    contract_type: Optional[str] = None,
) -> Dict[str, Any]:
    """業界・契約種別ごとのベンチマーク統計を取得する。"""
    logger.info(
        f"benchmark_stats called: industry={industry}, contract_type={contract_type}"
    )
    return await _get_service().get_stats(
        industry=industry, contract_type=contract_type
    )


async def benchmark_compare(contract_id: str) -> Dict[str, Any]:
    """指定契約を業界平均と比較し、乖離度を返す。"""
    logger.info(f"benchmark_compare called: contract_id={contract_id}")
    return await _get_service().compare_contract(contract_id)


def get_benchmark_stats_tool() -> FunctionTool:
    return FunctionTool.from_defaults(
        async_fn=benchmark_stats,
        name="benchmark_stats",
        description=(
            "Get benchmark statistics for contracts by industry and/or contract type. "
            "Returns aggregated stats: contract duration distribution (median, p25, p75), "
            "payment terms breakdown (net30/60/90), liability cap distribution, "
            "and auto-renewal rate. Use when the user asks about industry averages, "
            "market benchmarks, or typical contract terms."
        ),
    )


def get_benchmark_compare_tool() -> FunctionTool:
    return FunctionTool.from_defaults(
        async_fn=benchmark_compare,
        name="benchmark_compare",
        description=(
            "Compare a specific contract against industry benchmarks. "
            "Takes a contract_id and returns deviation analysis vs industry median "
            "for contract duration, liability cap, and other key metrics. "
            "Use when the user asks how a contract compares to industry standards."
        ),
    )
