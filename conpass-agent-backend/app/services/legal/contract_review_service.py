"""
review-contract: 契約レビュー（12条項カテゴリ並列AI解析）
PlaybookAPI から ClausePolicy を取得し、各条項を GREEN/YELLOW/RED に分類。
YELLOW/RED 条項にはリドライン（代替文言）を生成。
"""
import asyncio
import json
from typing import Optional

import httpx
from llama_index.llms.openai import OpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# --- 12 条項カテゴリ ---

CLAUSE_CATEGORIES = [
    "LIABILITY",
    "INDEMNIFICATION",
    "IP",
    "DATA_PROTECTION",
    "CONFIDENTIALITY",
    "WARRANTY",
    "TERMINATION",
    "GOVERNING_LAW",
    "INSURANCE",
    "ASSIGNMENT",
    "FORCE_MAJEURE",
    "PAYMENT",
]

CLAUSE_CATEGORY_LABELS = {
    "LIABILITY": "責任制限",
    "INDEMNIFICATION": "補償",
    "IP": "知的財産権",
    "DATA_PROTECTION": "データ保護",
    "CONFIDENTIALITY": "秘密保持",
    "WARRANTY": "保証",
    "TERMINATION": "契約解除",
    "GOVERNING_LAW": "準拠法・管轄",
    "INSURANCE": "保険",
    "ASSIGNMENT": "譲渡制限",
    "FORCE_MAJEURE": "不可抗力",
    "PAYMENT": "支払条件",
}


# --- Request / Response Models ---

class ReviewContext(BaseModel):
    side: str = "buyer"  # buyer / seller / neutral
    deadline: Optional[str] = None
    focus_areas: list[str] = []
    deal_context: dict = {}


class ContractReviewRequest(BaseModel):
    contract_id: str
    context: ReviewContext = ReviewContext()


class ClauseAnalysisItem(BaseModel):
    clause_type: str
    clause_label: str
    status: str  # GREEN / YELLOW / RED
    contract_says: str
    playbook_position: str
    deviation: str
    business_impact: str
    redline: str = ""
    rationale: str = ""
    priority: int = 0  # 1=最優先, 数字が大きいほど低優先


class ContractReviewResult(BaseModel):
    contract_id: str
    review_basis: str  # "playbook" | "generic"
    clause_analysis: list[ClauseAnalysisItem]
    negotiation_strategy: dict
    next_steps: list[str]


# --- LLM Prompt ---

CLAUSE_REVIEW_PROMPT = """あなたは企業法務の契約レビュー専門家です。

以下の契約テキストから、指定された条項カテゴリを分析してください。

## 契約テキスト
{contract_text}

## 分析対象カテゴリ
{clause_type} ({clause_label})

## レビュー観点
立場: {side}
{playbook_instruction}

## 出力指示
以下の JSON 形式で回答してください。他のテキストは一切含めないでください。

{{
  "status": "GREEN or YELLOW or RED",
  "contract_says": "契約書の当該条項の要約（日本語100文字以内）",
  "deviation": "基準からの乖離点（日本語、なければ空文字）",
  "business_impact": "ビジネスへの影響（日本語100文字以内）",
  "redline": "代替文言の提案（YELLOWまたはREDの場合のみ。GREENの場合は空文字）",
  "rationale": "判定理由（日本語50文字以内）",
  "priority": 1-12の整数（1が最優先）
}}

判定基準:
- GREEN: 当社にとって有利または標準的。修正不要。
- YELLOW: 注意が必要。交渉で改善の余地あり。
- RED: 当社にとって不利。修正を強く推奨。
"""


# --- Service ---

DJANGO_API_TIMEOUT = httpx.Timeout(10.0)


class ContractReviewService:
    """契約レビューサービス（12条項並列AI解析）"""

    def __init__(self, conpass_jwt: Optional[str] = None):
        self.base_url = settings.CONPASS_API_BASE_URL
        self.cookie = f"auth-token={conpass_jwt};" if conpass_jwt else ""

    async def review(self, request: ContractReviewRequest) -> ContractReviewResult:
        # 1. 契約テキスト取得
        contract_text = await self._fetch_contract_text(request.contract_id)
        if not contract_text:
            raise ValueError(f"Contract {request.contract_id} text could not be retrieved")

        # 2. Playbook ClausePolicy 取得（Django API）
        playbook_policies = await self._fetch_playbook_policies()
        review_basis = "playbook" if playbook_policies else "generic"

        # 3. 12条項カテゴリを並列解析
        tasks = [
            self._analyze_clause(
                contract_text=contract_text,
                clause_type=cat,
                side=request.context.side,
                playbook_policy=playbook_policies.get(cat),
            )
            for cat in CLAUSE_CATEGORIES
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        clause_analysis: list[ClauseAnalysisItem] = []
        for idx, result in enumerate(results):
            cat = CLAUSE_CATEGORIES[idx]
            if isinstance(result, Exception):
                logger.error("Clause analysis failed for %s: %s", cat, result)
                clause_analysis.append(
                    ClauseAnalysisItem(
                        clause_type=cat,
                        clause_label=CLAUSE_CATEGORY_LABELS.get(cat, cat),
                        status="YELLOW",
                        contract_says="分析中にエラーが発生しました",
                        playbook_position="N/A",
                        deviation="N/A",
                        business_impact="評価不能",
                        rationale=str(result),
                        priority=99,
                    )
                )
            else:
                clause_analysis.append(result)

        # 優先度でソート
        clause_analysis.sort(key=lambda x: x.priority)

        # 4. 交渉戦略と次ステップ
        negotiation_strategy = self._build_negotiation_strategy(
            clause_analysis, request.context
        )
        next_steps = self._build_next_steps(clause_analysis, review_basis)

        return ContractReviewResult(
            contract_id=request.contract_id,
            review_basis=review_basis,
            clause_analysis=clause_analysis,
            negotiation_strategy=negotiation_strategy,
            next_steps=next_steps,
        )

    async def _fetch_contract_text(self, contract_id: str) -> Optional[str]:
        """ConPass API から契約テキスト取得"""
        try:
            async with httpx.AsyncClient(timeout=DJANGO_API_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/contract/body/list",
                    headers={"Cookie": self.cookie},
                    params={"id": contract_id},
                )
                resp.raise_for_status()
                data = resp.json()

            if isinstance(data, dict) and "response" in data:
                response_list = data["response"]
                if isinstance(response_list, list) and len(response_list) > 0:
                    first_item = response_list[0]
                    if isinstance(first_item, dict) and "body" in first_item:
                        body_obj = first_item["body"]
                        if isinstance(body_obj, dict) and "body" in body_obj:
                            from urllib.parse import unquote
                            return unquote(body_obj["body"])
            return None
        except Exception as exc:
            logger.error("Failed to fetch contract text for %s: %s", contract_id, exc)
            return None

    async def _fetch_playbook_policies(self) -> dict[str, str]:
        """Django PlaybookAPI から ClausePolicy を取得
        1. GET /api/v1/tenant/playbook/ でPlaybook一覧を取得
        2. デフォルト（またはアクティブな最初の）Playbookを選択
        3. GET /api/v1/tenant/playbook/{id}/clauses/ でClausePolicyを取得
        未取得時は空dictを返し、generic commercial standardsにフォールバック
        """
        try:
            # Playbook一覧を取得してデフォルトIDを特定
            playbook_id = await self._get_default_playbook_id()
            if not playbook_id:
                logger.info("No playbook found, using generic standards")
                return {}

            async with httpx.AsyncClient(timeout=DJANGO_API_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/tenant/playbook/{playbook_id}/clauses/",
                    headers={"Cookie": self.cookie},
                )
                if resp.status_code != 200:
                    logger.info(
                        "Playbook clauses API returned %s, using generic standards",
                        resp.status_code,
                    )
                    return {}
                data = resp.json()

            policies = {}
            if isinstance(data, list):
                for item in data:
                    clause_type = item.get("clause_type", "").upper()
                    position = item.get("position", "")
                    if clause_type and position:
                        policies[clause_type] = position
            return policies
        except Exception as exc:
            logger.warning("Failed to fetch playbook policies: %s", exc)
            return {}

    async def _get_default_playbook_id(self) -> Optional[str]:
        """Playbook一覧からデフォルト（またはアクティブな最初の）IDを返す"""
        try:
            async with httpx.AsyncClient(timeout=DJANGO_API_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/tenant/playbook/",
                    headers={"Cookie": self.cookie},
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()

            if isinstance(data, list) and data:
                # is_default フラグがあればそれを優先、なければ最初のものを使用
                for pb in data:
                    if pb.get("is_default"):
                        return str(pb["id"])
                return str(data[0]["id"])
            if isinstance(data, dict) and "results" in data:
                results = data["results"]
                if results:
                    for pb in results:
                        if pb.get("is_default"):
                            return str(pb["id"])
                    return str(results[0]["id"])
            return None
        except Exception as exc:
            logger.warning("Failed to fetch playbook list: %s", exc)
            return None

    async def _analyze_clause(
        self,
        contract_text: str,
        clause_type: str,
        side: str,
        playbook_policy: Optional[str],
    ) -> ClauseAnalysisItem:
        """単一条項を LLM で解析"""
        clause_label = CLAUSE_CATEGORY_LABELS.get(clause_type, clause_type)

        if playbook_policy:
            playbook_instruction = f"Playbook ポジション: {playbook_policy}"
        else:
            playbook_instruction = "Playbook 未設定。一般的な商取引基準で評価してください。"

        prompt = CLAUSE_REVIEW_PROMPT.format(
            contract_text=contract_text,
            clause_type=clause_type,
            clause_label=clause_label,
            side=side,
            playbook_instruction=playbook_instruction,
        )

        llm = OpenAI(
            model="gpt-4o",
            temperature=0.2,
            api_key=settings.OPENAI_API_KEY,
            timeout=90,
            max_retries=1,
        )

        response = await llm.acomplete(prompt)
        raw_text = response.text.strip()

        try:
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[-1]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response for %s", clause_type)
            parsed = {}

        status_val = parsed.get("status", "YELLOW").upper()
        if status_val not in ("GREEN", "YELLOW", "RED"):
            status_val = "YELLOW"

        return ClauseAnalysisItem(
            clause_type=clause_type,
            clause_label=clause_label,
            status=status_val,
            contract_says=parsed.get("contract_says", ""),
            playbook_position=playbook_policy or "一般商取引基準",
            deviation=parsed.get("deviation", ""),
            business_impact=parsed.get("business_impact", ""),
            redline=parsed.get("redline", ""),
            rationale=parsed.get("rationale", ""),
            priority=parsed.get("priority", 99),
        )

    @staticmethod
    def _build_negotiation_strategy(
        analysis: list[ClauseAnalysisItem], context: ReviewContext
    ) -> dict:
        red_items = [a for a in analysis if a.status == "RED"]
        yellow_items = [a for a in analysis if a.status == "YELLOW"]

        strategy = {
            "overall_risk": "HIGH" if red_items else ("MEDIUM" if yellow_items else "LOW"),
            "red_count": len(red_items),
            "yellow_count": len(yellow_items),
            "green_count": len(analysis) - len(red_items) - len(yellow_items),
            "priority_issues": [
                {
                    "clause": a.clause_label,
                    "impact": a.business_impact,
                    "proposed_change": a.redline,
                }
                for a in red_items[:5]
            ],
            "side": context.side,
        }
        if context.deadline:
            strategy["deadline"] = context.deadline
        return strategy

    @staticmethod
    def _build_next_steps(
        analysis: list[ClauseAnalysisItem], review_basis: str
    ) -> list[str]:
        steps = []
        red_items = [a for a in analysis if a.status == "RED"]
        yellow_items = [a for a in analysis if a.status == "YELLOW"]

        if red_items:
            steps.append(
                f"RED条項 {len(red_items)}件 の修正交渉を最優先で実施してください"
            )
            for a in red_items[:3]:
                steps.append(f"  - {a.clause_label}: {a.rationale}")

        if yellow_items:
            steps.append(
                f"YELLOW条項 {len(yellow_items)}件 について交渉の余地を検討してください"
            )

        if review_basis == "generic":
            steps.append(
                "Playbook が未設定です。自社の契約ポリシーを設定することで精度が向上します"
            )

        if not red_items and not yellow_items:
            steps.append("全条項が GREEN です。署名プロセスに進めます")

        return steps
