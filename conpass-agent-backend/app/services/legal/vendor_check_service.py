"""
vendor-check: 取引先横断チェック（Multi-Source Aggregation Pattern）
5ソース並列検索 -> 結果集約 -> Gap Analysis -> アクションアイテム生成
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

CONPASS_API_TIMEOUT = httpx.Timeout(15.0)


# --- Request / Response Models ---

class VendorCheckRequest(BaseModel):
    vendor_name: str
    account_id: str


class AgreementSummary(BaseModel):
    agreement_type: str  # NDA / MSA / SOW / DPA / SLA 等
    status: str  # ACTIVE / EXPIRED / IN_NEGOTIATION / PENDING
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    auto_renewal: bool = False
    key_terms: str = ""
    contract_id: Optional[str] = None


class GapAnalysis(BaseModel):
    required_missing: list[str]  # 不足している契約種別
    expiring_within_90_days: list[dict]
    sources_unavailable: list[str]


class VendorCheckResult(BaseModel):
    vendor_name: str
    search_date: str
    sources_checked: list[str]
    sources_unavailable: list[str]
    relationship_overview: dict
    agreement_summary: list[AgreementSummary]
    gap_analysis: GapAnalysis
    upcoming_actions: list[str]
    rule_alerts: list[dict]


# --- Service ---

# 取引に通常必要とされる契約種別
REQUIRED_AGREEMENT_TYPES = ["NDA", "MSA", "SOW", "DPA", "SLA"]

SOURCE_NAMES = ["CLM", "CRM", "Storage", "MailHistory", "RAG"]


class VendorCheckService:
    """取引先横断チェックサービス"""

    def __init__(self, conpass_jwt: Optional[str] = None):
        self.base_url = settings.CONPASS_API_BASE_URL
        self.cookie = f"auth-token={conpass_jwt};" if conpass_jwt else ""

    async def check(self, request: VendorCheckRequest) -> VendorCheckResult:
        """5ソース並列検索 -> 集約 -> Gap Analysis"""
        sources_unavailable: list[str] = []

        tasks = [
            self._search_clm(request),
            self._search_crm(request),
            self._search_storage(request),
            self._search_mail_history(request),
            self._search_rag(request),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_agreements: list[AgreementSummary] = []
        relationship_data: dict = {}

        for idx, result in enumerate(results):
            source_name = SOURCE_NAMES[idx]
            if isinstance(result, Exception):
                logger.warning(
                    "Source %s failed for vendor %s: %s",
                    source_name, request.vendor_name, result,
                )
                sources_unavailable.append(source_name)
                continue

            agreements, rel_fragment = result
            all_agreements.extend(agreements)
            relationship_data.update(rel_fragment)

        gap_analysis = self._run_gap_analysis(all_agreements, sources_unavailable)
        upcoming_actions = self._build_upcoming_actions(all_agreements, gap_analysis)
        rule_alerts = self._check_rules(all_agreements)

        return VendorCheckResult(
            vendor_name=request.vendor_name,
            search_date=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            sources_checked=[s for s in SOURCE_NAMES if s not in sources_unavailable],
            sources_unavailable=sources_unavailable,
            relationship_overview=relationship_data,
            agreement_summary=all_agreements,
            gap_analysis=gap_analysis,
            upcoming_actions=upcoming_actions,
            rule_alerts=rule_alerts,
        )

    # ---- 個別ソース検索 ----

    async def _search_clm(
        self, request: VendorCheckRequest
    ) -> tuple[list[AgreementSummary], dict]:
        """CLM (Contract Lifecycle Management) からの契約検索"""
        try:
            async with httpx.AsyncClient(timeout=CONPASS_API_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/contract/paginate",
                    headers={"Cookie": self.cookie},
                    params={
                        "keyword": request.vendor_name,
                        "accountId": request.account_id,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            contracts = []
            if isinstance(data, dict):
                contracts = data.get("response", {}).get("data", [])
                if not isinstance(contracts, list):
                    contracts = []

            agreements = []
            for c in contracts:
                agreements.append(
                    AgreementSummary(
                        agreement_type=c.get("contractType", "UNKNOWN"),
                        status=self._map_contract_status(c.get("status")),
                        effective_date=c.get("effectiveDate"),
                        expiration_date=c.get("expirationDate"),
                        auto_renewal=bool(c.get("autoRenewal", False)),
                        key_terms=c.get("summary", ""),
                        contract_id=str(c.get("id", "")),
                    )
                )

            return agreements, {"clm_total_contracts": len(agreements)}

        except Exception as exc:
            logger.error("CLM search failed: %s", exc)
            raise

    async def _search_crm(
        self, request: VendorCheckRequest
    ) -> tuple[list[AgreementSummary], dict]:
        """CRM からの取引先情報取得（プロトタイプ: スタブ実装）"""
        # CRM 連携は将来実装。現状はスタブとして空結果を返す。
        return [], {"crm_status": "not_connected"}

    async def _search_storage(
        self, request: VendorCheckRequest
    ) -> tuple[list[AgreementSummary], dict]:
        """ストレージ（GCS/SharePoint等）からの文書検索（プロトタイプ: スタブ実装）"""
        return [], {"storage_status": "not_connected"}

    async def _search_mail_history(
        self, request: VendorCheckRequest
    ) -> tuple[list[AgreementSummary], dict]:
        """メール履歴からの関連文書検索（プロトタイプ: スタブ実装）"""
        return [], {"mail_status": "not_connected"}

    async def _search_rag(
        self, request: VendorCheckRequest
    ) -> tuple[list[AgreementSummary], dict]:
        """RAG (セマンティック検索) による関連契約検索"""
        try:
            from app.services.chatbot.tools.semantic_search.semantic_search_tool import (
                semantic_search,
            )
            # semantic_search は directory_ids が必要だが、vendor-check 横断では
            # 全ディレクトリを対象とする。account_id から取得する設計だが
            # プロトタイプでは空リストで呼び出す（フィルタなし）。
            results = await semantic_search(
                directory_ids=[],
                query=f"取引先 {request.vendor_name} 契約",
                similarity_top_k=20,
                deduplicate_by_contract=True,
            )

            agreements = []
            for src in results:
                if "error" in src:
                    continue
                metadata = src.get("metadata", {})
                agreements.append(
                    AgreementSummary(
                        agreement_type=metadata.get("contract_type", "UNKNOWN"),
                        status="ACTIVE",
                        key_terms=src.get("excerpt", "")[:200],
                        contract_id=str(src.get("contract_id", "")),
                    )
                )

            return agreements, {"rag_hits": len(agreements)}

        except Exception as exc:
            logger.error("RAG search failed: %s", exc)
            raise

    # ---- 分析ヘルパー ----

    @staticmethod
    def _map_contract_status(raw_status) -> str:
        mapping = {
            1: "ACTIVE",
            2: "EXPIRED",
            3: "IN_NEGOTIATION",
            4: "PENDING",
        }
        if isinstance(raw_status, int):
            return mapping.get(raw_status, "UNKNOWN")
        if isinstance(raw_status, str):
            return raw_status.upper()
        return "UNKNOWN"

    @staticmethod
    def _run_gap_analysis(
        agreements: list[AgreementSummary],
        sources_unavailable: list[str],
    ) -> GapAnalysis:
        existing_types = {a.agreement_type.upper() for a in agreements}
        required_missing = [
            t for t in REQUIRED_AGREEMENT_TYPES if t not in existing_types
        ]

        now = datetime.utcnow()
        threshold = now + timedelta(days=90)
        expiring_soon = []
        for a in agreements:
            if a.expiration_date:
                try:
                    exp = datetime.fromisoformat(a.expiration_date.replace("Z", "+00:00"))
                    if exp.replace(tzinfo=None) <= threshold:
                        expiring_soon.append({
                            "agreement_type": a.agreement_type,
                            "contract_id": a.contract_id,
                            "expiration_date": a.expiration_date,
                        })
                except (ValueError, TypeError):
                    pass

        return GapAnalysis(
            required_missing=required_missing,
            expiring_within_90_days=expiring_soon,
            sources_unavailable=sources_unavailable,
        )

    @staticmethod
    def _build_upcoming_actions(
        agreements: list[AgreementSummary],
        gap: GapAnalysis,
    ) -> list[str]:
        actions = []
        if gap.required_missing:
            actions.append(
                f"不足契約の締結検討: {', '.join(gap.required_missing)}"
            )
        for item in gap.expiring_within_90_days:
            actions.append(
                f"契約更新対応: {item['agreement_type']} "
                f"(ID: {item.get('contract_id', 'N/A')}, "
                f"期限: {item.get('expiration_date', 'N/A')})"
            )
        if gap.sources_unavailable:
            actions.append(
                f"未接続データソースの確認: {', '.join(gap.sources_unavailable)}"
            )
        return actions

    @staticmethod
    def _check_rules(agreements: list[AgreementSummary]) -> list[dict]:
        alerts = []
        for a in agreements:
            if a.status == "EXPIRED":
                alerts.append({
                    "rule": "expired_agreement",
                    "severity": "HIGH",
                    "message": f"{a.agreement_type} (ID: {a.contract_id}) は期限切れです",
                })
            if a.agreement_type.upper() == "NDA" and not a.auto_renewal:
                alerts.append({
                    "rule": "nda_no_auto_renewal",
                    "severity": "MEDIUM",
                    "message": f"NDA (ID: {a.contract_id}) に自動更新条項がありません",
                })
        return alerts
