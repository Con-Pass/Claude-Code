import json
from typing import Any, Dict, List

from llama_index.llms.openai import OpenAIResponses
from app.core.logging_config import get_logger
from datetime import datetime
from app.core.config import settings
from app.schemas.contract_tools import RiskAnalysis
from app.schemas.general import GeneralResponse
from app.services.chatbot.tools.risk_analysis.prompts import (
    RISK_ANALYSIS_PROMPT_TEMPLATE,
    LAW_COMPLIANCE_CHECK_PROMPT_TEMPLATE,
)

logger = get_logger(__name__)


async def perform_risk_analysis(body: str) -> GeneralResponse:
    try:
        today = datetime.now().strftime("%Y-%m-%d")

        prompt = RISK_ANALYSIS_PROMPT_TEMPLATE.format(today=today, contract_body=body)

        llm = OpenAIResponses(
            model="gpt-5-mini",
            temperature=0.4,
            api_key=settings.OPENAI_API_KEY,
            reasoning_options={"effort": "minimal"},
            timeout=120,
            max_retries=1,
        )

        sllm = llm.as_structured_llm(RiskAnalysis)

        response = await sllm.acomplete(prompt)

        res_data = response.model_dump().get("raw", {})
        return GeneralResponse(
            status="success",
            description="Risk analysis performed successfully",
            data=res_data,
        )
    except Exception:
        logger.exception("Error performing risk analysis")
        return GeneralResponse(
            status="error",
            description="Error performing risk analysis",
        )


async def perform_law_compliance_check(
    contract_body: str,
    related_laws: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    契約書と関連法令条文をGPT-4oで比較し、法令適合性の問題を特定する。

    Args:
        contract_body: 契約書本文
        related_laws: 関連法令のリスト（semantic_searchの結果）

    Returns:
        法令適合性の問題リスト:
        [{"law_name": str, "article": str, "issue": str, "severity": "HIGH"|"MEDIUM"|"LOW"}]
    """
    try:
        # 関連法令テキストを整形
        law_context_parts = []
        for law in related_laws:
            law_text = (
                f"【{law.get('law_name', '')} {law.get('article_number', '')}】\n"
                f"{law.get('excerpt', '')}"
            )
            law_context_parts.append(law_text)

        law_context = "\n\n".join(law_context_parts)

        prompt = LAW_COMPLIANCE_CHECK_PROMPT_TEMPLATE.format(
            contract_body=contract_body[:3000],  # トークン節約のため先頭3000文字
            law_context=law_context,
        )

        llm = OpenAIResponses(
            model="gpt-5-mini",
            temperature=0.3,
            api_key=settings.OPENAI_API_KEY,
            timeout=90,
            max_retries=1,
        )

        response = await llm.acomplete(prompt)
        response_text = str(response).strip()

        # JSONパース
        issues = json.loads(response_text)
        if not isinstance(issues, list):
            issues = []

        # バリデーション
        valid_issues = []
        for issue in issues:
            if (
                isinstance(issue, dict)
                and "law_name" in issue
                and "article" in issue
                and "issue" in issue
                and issue.get("severity") in ("HIGH", "MEDIUM", "LOW")
            ):
                valid_issues.append({
                    "law_name": issue["law_name"],
                    "article": issue["article"],
                    "issue": issue["issue"],
                    "severity": issue["severity"],
                })

        logger.info(f"Law compliance check found {len(valid_issues)} issues")
        return valid_issues

    except json.JSONDecodeError:
        logger.warning("Failed to parse law compliance check response as JSON")
        return []
    except Exception:
        logger.exception("Error performing law compliance check")
        return []
