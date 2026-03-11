"""
brief: 法務ブリーフィング（daily / topic / incident の3モード）
各モードに応じたソース集約・分析を実行。
"""
import asyncio
from datetime import datetime
from typing import Optional

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

API_TIMEOUT = httpx.Timeout(15.0)


# --- Request / Response Models ---

class LegalBriefRequest(BaseModel):
    mode: str = "daily"  # daily / topic / incident
    query: Optional[str] = None
    account_id: str = ""


class BriefSection(BaseModel):
    title: str
    items: list[dict]
    source: str


class LegalBriefResult(BaseModel):
    mode: str
    generated_at: str
    sections: list[BriefSection]
    summary: str
    action_items: list[str]


# --- Service ---

class LegalBriefService:
    """法務ブリーフィングサービス"""

    def __init__(self, conpass_jwt: Optional[str] = None):
        self.base_url = settings.CONPASS_API_BASE_URL
        self.cookie = f"auth-token={conpass_jwt};" if conpass_jwt else ""

    async def generate(self, request: LegalBriefRequest) -> LegalBriefResult:
        if request.mode == "daily":
            return await self._daily_brief(request)
        elif request.mode == "topic":
            return await self._topic_brief(request)
        elif request.mode == "incident":
            return await self._incident_brief(request)
        else:
            raise ValueError(f"Unsupported brief mode: {request.mode}")

    # ---- daily モード ----

    async def _daily_brief(self, request: LegalBriefRequest) -> LegalBriefResult:
        """5ソース並列集約で日次ブリーフィングを生成"""
        tasks = [
            self._fetch_pending_reviews(),
            self._fetch_expiring_contracts(),
            self._fetch_new_contracts(),
            self._fetch_rule_alerts(),
            self._fetch_signing_status(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        sections: list[BriefSection] = []
        action_items: list[str] = []

        # レビュー待ち契約
        if not isinstance(results[0], Exception) and results[0]:
            sections.append(BriefSection(
                title="レビュー待ち契約",
                items=results[0],
                source="CLM",
            ))
            action_items.append(f"レビュー待ち {len(results[0])}件 の確認が必要です")

        # 30日以内期限切れ
        if not isinstance(results[1], Exception) and results[1]:
            sections.append(BriefSection(
                title="30日以内に期限切れの契約",
                items=results[1],
                source="CLM",
            ))
            action_items.append(f"期限切れ間近 {len(results[1])}件 の更新対応が必要です")

        # 新規締結
        if not isinstance(results[2], Exception) and results[2]:
            sections.append(BriefSection(
                title="新規締結契約",
                items=results[2],
                source="CLM",
            ))

        # 未対応アラート
        if not isinstance(results[3], Exception) and results[3]:
            sections.append(BriefSection(
                title="未対応ルールアラート",
                items=results[3],
                source="RuleEngine",
            ))
            action_items.append(f"未対応アラート {len(results[3])}件 への対応が必要です")

        # 署名待ち
        if not isinstance(results[4], Exception) and results[4]:
            sections.append(BriefSection(
                title="署名待ちステータス",
                items=results[4],
                source="GMO Sign",
            ))

        summary = self._build_daily_summary(sections, action_items)

        return LegalBriefResult(
            mode="daily",
            generated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            sections=sections,
            summary=summary,
            action_items=action_items,
        )

    # ---- topic モード ----

    async def _topic_brief(self, request: LegalBriefRequest) -> LegalBriefResult:
        """RAG横断検索でトピック別ブリーフィングを生成"""
        if not request.query:
            raise ValueError("topic mode requires a query parameter")

        sections: list[BriefSection] = []
        action_items: list[str] = []

        # RAG 横断検索
        rag_results = await self._search_rag(request.query)
        if rag_results:
            sections.append(BriefSection(
                title=f"トピック: {request.query}",
                items=rag_results,
                source="RAG",
            ))
            action_items.append(f"{len(rag_results)}件 の関連契約が見つかりました")

        summary = f"トピック「{request.query}」に関するブリーフィング。{len(rag_results)}件の関連契約を検出。"

        return LegalBriefResult(
            mode="topic",
            generated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            sections=sections,
            summary=summary,
            action_items=action_items,
        )

    # ---- incident モード ----

    async def _incident_brief(self, request: LegalBriefRequest) -> LegalBriefResult:
        """全ソース緊急検索でインシデント対応ブリーフィングを生成"""
        if not request.query:
            raise ValueError("incident mode requires a query parameter")

        tasks = [
            self._search_rag(f"免責 補償 {request.query}"),
            self._search_rag(f"保険 {request.query}"),
            self._search_rag(f"秘密保持 データ保護 {request.query}"),
            self._fetch_rule_alerts(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        sections: list[BriefSection] = []
        action_items: list[str] = []

        labels = ["免責・補償関連", "保険関連", "守秘義務・データ保護関連"]
        for idx, label in enumerate(labels):
            if not isinstance(results[idx], Exception) and results[idx]:
                sections.append(BriefSection(
                    title=label,
                    items=results[idx],
                    source="RAG",
                ))

        if not isinstance(results[3], Exception) and results[3]:
            sections.append(BriefSection(
                title="関連ルールアラート",
                items=results[3],
                source="RuleEngine",
            ))

        # 法定対応期限の自動特定
        deadlines = self._identify_regulatory_deadlines(request.query)
        if deadlines:
            action_items.extend(deadlines)

        action_items.append("インシデント対応チームへの報告を確認してください")

        summary = (
            f"インシデント「{request.query}」に関する緊急ブリーフィング。"
            f"{sum(len(s.items) for s in sections)}件の関連情報を検出。"
        )

        return LegalBriefResult(
            mode="incident",
            generated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            sections=sections,
            summary=summary,
            action_items=action_items,
        )

    # ---- データソース取得 ----

    async def _fetch_pending_reviews(self) -> list[dict]:
        """レビュー待ち契約をCLMから取得"""
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/contract/paginate",
                    headers={"Cookie": self.cookie},
                    params={"status": "pending_review"},
                )
                resp.raise_for_status()
                data = resp.json()
            contracts = data.get("response", {}).get("data", [])
            if not isinstance(contracts, list):
                return []
            return [
                {
                    "contract_id": c.get("id"),
                    "title": c.get("title", ""),
                    "status": c.get("status", ""),
                    "created_at": c.get("createdAt", ""),
                }
                for c in contracts[:20]
            ]
        except Exception as exc:
            logger.warning("Failed to fetch pending reviews: %s", exc)
            return []

    async def _fetch_expiring_contracts(self) -> list[dict]:
        """30日以内に期限切れの契約を取得"""
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/contract/paginate",
                    headers={"Cookie": self.cookie},
                    params={"expiring_within_days": 30},
                )
                resp.raise_for_status()
                data = resp.json()
            contracts = data.get("response", {}).get("data", [])
            if not isinstance(contracts, list):
                return []
            return [
                {
                    "contract_id": c.get("id"),
                    "title": c.get("title", ""),
                    "expiration_date": c.get("expirationDate", ""),
                    "auto_renewal": c.get("autoRenewal", False),
                }
                for c in contracts[:20]
            ]
        except Exception as exc:
            logger.warning("Failed to fetch expiring contracts: %s", exc)
            return []

    async def _fetch_new_contracts(self) -> list[dict]:
        """新規締結契約を取得"""
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/contract/paginate",
                    headers={"Cookie": self.cookie},
                    params={"status": "newly_executed", "limit": 10},
                )
                resp.raise_for_status()
                data = resp.json()
            contracts = data.get("response", {}).get("data", [])
            if not isinstance(contracts, list):
                return []
            return [
                {
                    "contract_id": c.get("id"),
                    "title": c.get("title", ""),
                    "executed_date": c.get("effectiveDate", ""),
                }
                for c in contracts[:10]
            ]
        except Exception as exc:
            logger.warning("Failed to fetch new contracts: %s", exc)
            return []

    async def _fetch_rule_alerts(self) -> list[dict]:
        """Django RuleEvaluationLog API から未対応アラートを取得"""
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/tenant/rule-evaluations/",
                    headers={"Cookie": self.cookie},
                    params={"status": "unresolved", "severity__in": "WARN,FAIL"},
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
            if isinstance(data, list):
                return [
                    {
                        "rule_id": a.get("rule_id"),
                        "severity": a.get("severity"),
                        "message": a.get("message", ""),
                        "contract_id": a.get("contract_id"),
                        "evaluated_at": a.get("evaluated_at", ""),
                    }
                    for a in data[:20]
                ]
            return []
        except Exception as exc:
            logger.warning("Failed to fetch rule alerts: %s", exc)
            return []

    async def _fetch_signing_status(self) -> list[dict]:
        """GMO Sign API から署名待ちステータスを取得（プロトタイプ: スタブ）"""
        # GMO Sign 連携は将来実装
        return []

    async def _search_rag(self, query: str) -> list[dict]:
        """RAG セマンティック検索"""
        try:
            from app.services.chatbot.tools.semantic_search.semantic_search_tool import (
                semantic_search,
            )
            results = await semantic_search(
                directory_ids=[],
                query=query,
                similarity_top_k=10,
                deduplicate_by_contract=True,
            )
            return [
                {
                    "contract_id": r.get("contract_id"),
                    "excerpt": r.get("excerpt", "")[:200],
                    "score": r.get("score", 0),
                    "metadata": r.get("metadata", {}),
                }
                for r in results
                if "error" not in r
            ]
        except Exception as exc:
            logger.warning("RAG search failed: %s", exc)
            return []

    @staticmethod
    def _identify_regulatory_deadlines(query: str) -> list[str]:
        """クエリに基づく法定対応期限の自動特定"""
        deadlines = []
        query_lower = query.lower()

        if "gdpr" in query_lower or "データ漏洩" in query_lower or "個人情報" in query_lower:
            deadlines.append("GDPR: データ侵害通知は72時間以内（監督機関）")
        if "pci" in query_lower:
            deadlines.append("PCI DSS: インシデント報告は24時間以内")
        if "不正アクセス" in query_lower:
            deadlines.append("不正アクセス禁止法: 速やかに警察へ届出")
        if "個人情報" in query_lower or "漏洩" in query_lower:
            deadlines.append("個人情報保護法: 個人情報保護委員会への報告（速報3-5日、確報30日）")

        return deadlines

    @staticmethod
    def _build_daily_summary(
        sections: list[BriefSection], action_items: list[str]
    ) -> str:
        total_items = sum(len(s.items) for s in sections)
        return (
            f"本日の法務ブリーフィング: {len(sections)}セクション、"
            f"合計{total_items}件の情報。"
            f"要対応: {len(action_items)}件。"
        )
