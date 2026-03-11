"""
ベンチマークDB: Qdrantの契約データから匿名化統計を生成
業界・契約種別ごとの集計統計と、指定契約の業界平均比較を提供する
"""
import json
import hashlib
from typing import Optional

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# キャッシュTTL(秒) - デフォルト1時間
BENCHMARK_CACHE_TTL = int(getattr(settings, "BENCHMARK_CACHE_TTL_SECONDS", 3600))


class BenchmarkService:
    """契約ベンチマークデータの集計・比較サービス"""

    def __init__(self):
        self._qdrant_url = settings.QDRANT_URL
        self._qdrant_api_key = settings.QDRANT_API_KEY
        self._collection = settings.QDRANT_COLLECTION
        self._redis_url = settings.REDIS_URL

    def _cache_key(self, prefix: str, **kwargs) -> str:
        """キャッシュキーを生成する"""
        raw = json.dumps(kwargs, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"benchmark:{prefix}:{digest}"

    async def _get_cached(self, key: str) -> Optional[dict]:
        """Redisキャッシュからデータを取得する"""
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(self._redis_url, decode_responses=True)
            try:
                cached = await r.get(key)
                if cached:
                    return json.loads(cached)
                return None
            finally:
                await r.aclose()
        except Exception as e:
            logger.warning(f"Redis cache read failed: {e}")
            return None

    async def _set_cached(self, key: str, data: dict, ttl: int = BENCHMARK_CACHE_TTL) -> None:
        """Redisキャッシュにデータを保存する"""
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(self._redis_url, decode_responses=True)
            try:
                await r.setex(key, ttl, json.dumps(data, ensure_ascii=False))
            finally:
                await r.aclose()
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")

    async def _query_qdrant_contracts(
        self, industry: Optional[str] = None, contract_type: Optional[str] = None
    ) -> list[dict]:
        """Qdrantから契約データのペイロードを取得する"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            client = QdrantClient(url=self._qdrant_url, api_key=self._qdrant_api_key)

            conditions = []
            if industry:
                conditions.append(
                    FieldCondition(key="industry", match=MatchValue(value=industry))
                )
            if contract_type:
                conditions.append(
                    FieldCondition(
                        key="contract_type", match=MatchValue(value=contract_type)
                    )
                )

            scroll_filter = Filter(must=conditions) if conditions else None

            results = []
            offset = None
            while True:
                response = client.scroll(
                    collection_name=self._collection,
                    scroll_filter=scroll_filter,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                points, next_offset = response
                for point in points:
                    if point.payload:
                        results.append(point.payload)
                if next_offset is None:
                    break
                offset = next_offset

            return results
        except Exception as e:
            logger.exception(f"Qdrant query error: {e}")
            return []

    def _compute_stats(self, contracts: list[dict]) -> dict:
        """契約データから匿名化統計を算出する"""
        if not contracts:
            return {
                "total_count": 0,
                "contract_duration": None,
                "payment_terms": None,
                "liability_cap": None,
                "auto_renewal_rate": None,
            }

        # 契約期間（月単位）の分布
        durations = []
        for c in contracts:
            dur = c.get("duration_months")
            if dur is not None:
                try:
                    durations.append(float(dur))
                except (ValueError, TypeError):
                    pass

        duration_stats = self._percentile_stats(durations) if durations else None

        # 支払条件の割合
        payment_counts = {"net30": 0, "net60": 0, "net90": 0, "other": 0}
        for c in contracts:
            term = str(c.get("payment_terms", "")).lower()
            if "net30" in term or "30" in term:
                payment_counts["net30"] += 1
            elif "net60" in term or "60" in term:
                payment_counts["net60"] += 1
            elif "net90" in term or "90" in term:
                payment_counts["net90"] += 1
            else:
                payment_counts["other"] += 1

        total = len(contracts)
        payment_rates = {k: round(v / total * 100, 1) for k, v in payment_counts.items()}

        # 損害賠償上限の分布
        liability_caps = []
        for c in contracts:
            cap = c.get("liability_cap")
            if cap is not None:
                try:
                    liability_caps.append(float(cap))
                except (ValueError, TypeError):
                    pass

        liability_stats = self._percentile_stats(liability_caps) if liability_caps else None

        # 自動更新条項の有無割合
        auto_renewal_count = sum(
            1 for c in contracts if c.get("auto_renewal") in (True, "true", "yes", 1)
        )
        auto_renewal_rate = round(auto_renewal_count / total * 100, 1)

        return {
            "total_count": total,
            "contract_duration": duration_stats,
            "payment_terms": payment_rates,
            "liability_cap": liability_stats,
            "auto_renewal_rate": auto_renewal_rate,
        }

    @staticmethod
    def _percentile_stats(values: list[float]) -> dict:
        """中央値・25/75パーセンタイルを算出する"""
        if not values:
            return {"median": None, "p25": None, "p75": None, "count": 0}

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        def percentile(pct: float) -> float:
            idx = (n - 1) * pct / 100.0
            lower = int(idx)
            upper = lower + 1
            if upper >= n:
                return sorted_vals[-1]
            frac = idx - lower
            return sorted_vals[lower] * (1 - frac) + sorted_vals[upper] * frac

        return {
            "median": round(percentile(50), 2),
            "p25": round(percentile(25), 2),
            "p75": round(percentile(75), 2),
            "count": n,
        }

    async def get_stats(
        self,
        industry: Optional[str] = None,
        contract_type: Optional[str] = None,
    ) -> dict:
        """
        業界・契約種別ごとのベンチマーク統計を返す。

        集計対象:
        - 契約期間の分布（median, p25, p75）
        - 支払条件（Net30/60/90の割合）
        - 損害賠償上限の分布
        - 自動更新条項の有無割合

        キャッシュ: Redisに1時間
        """
        cache_key = self._cache_key("stats", industry=industry, contract_type=contract_type)
        cached = await self._get_cached(cache_key)
        if cached:
            logger.info(f"Benchmark stats cache hit: {cache_key}")
            return cached

        contracts = await self._query_qdrant_contracts(industry, contract_type)
        stats = self._compute_stats(contracts)
        stats["filters"] = {"industry": industry, "contract_type": contract_type}

        await self._set_cached(cache_key, stats)
        return stats

    async def compare_contract(self, contract_id: str) -> dict:
        """
        指定契約を業界平均と比較し、乖離度を返す。

        1. 指定契約をQdrantから取得
        2. 同業界・同契約種別の統計を算出
        3. 各指標について乖離度を計算
        """
        cache_key = self._cache_key("compare", contract_id=contract_id)
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            client = QdrantClient(url=self._qdrant_url, api_key=self._qdrant_api_key)

            # 指定契約を取得
            search_result = client.scroll(
                collection_name=self._collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="contract_id",
                            match=MatchValue(value=contract_id),
                        )
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
            points, _ = search_result
            if not points:
                return {"error": f"Contract {contract_id} not found", "found": False}

            contract = points[0].payload
            industry = contract.get("industry")
            contract_type = contract.get("contract_type")

            # 業界統計を取得
            stats = await self.get_stats(industry=industry, contract_type=contract_type)

            # 乖離度を計算
            deviations = {}

            # 契約期間の乖離
            duration = contract.get("duration_months")
            if duration and stats.get("contract_duration"):
                median = stats["contract_duration"].get("median")
                if median and median > 0:
                    deviations["duration_months"] = {
                        "value": float(duration),
                        "industry_median": median,
                        "deviation_pct": round(
                            (float(duration) - median) / median * 100, 1
                        ),
                    }

            # 損害賠償上限の乖離
            liability = contract.get("liability_cap")
            if liability and stats.get("liability_cap"):
                median = stats["liability_cap"].get("median")
                if median and median > 0:
                    deviations["liability_cap"] = {
                        "value": float(liability),
                        "industry_median": median,
                        "deviation_pct": round(
                            (float(liability) - median) / median * 100, 1
                        ),
                    }

            result = {
                "found": True,
                "contract_id": contract_id,
                "industry": industry,
                "contract_type": contract_type,
                "industry_stats": stats,
                "deviations": deviations,
            }

            await self._set_cached(cache_key, result)
            return result
        except Exception as e:
            logger.exception(f"Compare contract error: {e}")
            return {"error": str(e), "found": False}
