from app.core.logging_config import get_logger
from datetime import datetime
from llama_index.core.tools import FunctionTool
from app.core.config import settings
from typing import Any, Dict, List, Optional
from app.services.conpass_api_service import ConpassApiService

from app.services.chatbot.tools.risk_analysis.perform_analysis import (
    perform_risk_analysis,
    perform_law_compliance_check,
)
from app.services.chatbot.tools.utils.document_store import get_document_from_docstore

logger = get_logger(__name__)

MAX_CONTRACTS_TO_ANALYZE = 2


async def risk_analysis(
    directory_ids: List[int], contract_ids: list[int], conpass_api_service: Optional[ConpassApiService] = None
) -> list[dict]:
    try:
        logger.info(
            f"risk_analysis tool called with directory_ids: {directory_ids} and contract_ids: {contract_ids}"
        )
        if len(contract_ids) > MAX_CONTRACTS_TO_ANALYZE:
            return [
                {
                    "summary_comment": f"Error: You can only analyze up to {MAX_CONTRACTS_TO_ANALYZE} contracts at a time.",
                }
            ]
        logger.info(f"Calling risk_analysis_tool with contract_ids: {contract_ids}")
        risk_analysis_list = []
        for contract_id in contract_ids:
            try:
                contract_response = await get_document_from_docstore(
                    directory_ids, contract_id, conpass_api_service
                )
                if not contract_response:
                    logger.warning(f"Contract {contract_id} not found in docstore")
                    risk_analysis_list.append(
                        {
                            "contract_id": contract_id,
                            "summary_comment": f"Contract {contract_id} not found in docstore",
                        }
                    )
                    continue
                contract_body = contract_response["full_text"]
                risk_analysis_result = await perform_risk_analysis(contract_body)
                if risk_analysis_result.status == "error":
                    logger.warning(
                        f"Error performing risk analysis for contract {contract_id}: {risk_analysis_result.description}"
                    )
                    risk_analysis_list.append(
                        {
                            "contract_id": contract_id,
                            "summary_comment": risk_analysis_result.description,
                        }
                    )
                    continue
                risk_analysis_data = risk_analysis_result.data if risk_analysis_result.data else {}
                risk_analysis_data["contract_id"] = contract_id
                risk_analysis_data["url"] = (
                    f"{settings.CONPASS_FRONTEND_BASE_URL}/contract/{contract_id}"
                )

                # 法令適合性チェック
                law_compliance_issues = await _check_law_compliance(
                    contract_body, directory_ids
                )
                if law_compliance_issues:
                    risk_analysis_data["law_compliance_issues"] = law_compliance_issues

                risk_analysis_list.append(risk_analysis_data)
                logger.info(
                    f"Risk analysis for contract {contract_id} performed successfully"
                )
            except Exception:
                logger.exception(
                    f"Error performing risk analysis for contract {contract_id}"
                )
                risk_analysis_list.append(
                    {
                        "contract_id": contract_id,
                        "summary_comment": f"Error performing risk analysis for contract {contract_id}",
                    }
                )

        return risk_analysis_list
    except Exception as e:
        logger.exception(f"Error performing risk analysis: {e}")
        return [
            {
                "error": "An unexpected error occurred while performing risk analysis",
            }
        ]


async def _check_law_compliance(
    contract_body: str,
    directory_ids: List[int],
) -> List[Dict[str, Any]]:
    """
    法令適合性チェックを実行する。

    1. 契約書の内容に関連する法令条文をlaw_regulationsコレクションから検索
    2. 関連条文と契約書をGPTで比較し、法令適合性の問題を特定

    Args:
        contract_body: 契約書本文
        directory_ids: ディレクトリID

    Returns:
        法令適合性の問題リスト
    """
    try:
        from app.services.chatbot.tools.semantic_search.semantic_search_tool import (
            _get_query_embedding,
            _search_law_regulations,
            LAW_QDRANT_COLLECTION,
        )

        # 契約書の要約的クエリを生成して関連法令を検索
        # 契約書の先頭部分をクエリとして使用（法令検索の精度向上のため）
        query_text = contract_body[:500]
        dense_embedding = await _get_query_embedding(query_text)

        related_laws = await _search_law_regulations(dense_embedding, top_k=5)

        if not related_laws:
            logger.info("No related laws found for compliance check")
            return []

        # GPTによる法令適合性チェック
        compliance_result = await perform_law_compliance_check(
            contract_body, related_laws
        )

        return compliance_result

    except Exception as e:
        logger.warning(f"Law compliance check failed (non-fatal): {e}")
        return []


def get_risk_analysis_tool(directory_ids: List[int], conpass_api_service: ConpassApiService) -> FunctionTool:
    today = datetime.now().strftime("%Y-%m-%d")
    return FunctionTool.from_defaults(
        async_fn=risk_analysis,
        name="risk_analysis_tool",
        description=f"""
        Today's date is {today}.

        Perform comprehensive AI-powered risk assessment on SPECIFIC contracts (by ID) (max {MAX_CONTRACTS_TO_ANALYZE} contracts per call). Fetches documents automatically and returns structured risk analysis in Japanese.

        Use this tool when
        - User explicitly asks to analyze/assess/evaluate RISKS or ISSUES in specified contracts
        - User requests problem spotting, red-flag review, or risk evaluation (legal/financial/operational/compliance/reputational/strategic)
        - User wants to identify what to negotiate or potential problems
        - Keywords: "analyze risks", "what are the risks", "identify issues", "what should we negotiate"

        Do NOT use this tool when
        - User only wants to read/view contract text → use read_contracts_tool instead
        - User asks general content questions or summaries → use read_contracts_tool instead
        - User wants to find/list contracts → use metadata_search or semantic_search instead
        - No specific contract IDs provided yet

        Critical routing examples
        - "Analyze the risks in contract 1234" → risk_analysis_tool ✓ (risk assessment)
        - "What should we negotiate in contract 5678?" → risk_analysis_tool ✓ (risk assessment)
        - "What are the SLA terms in contract 4824?" → read_contracts_tool ✓ (content extraction, not risk)
        - "Which contracts have high-risk clauses?" → semantic_search ✓ (discover across many)

        Args:
            contract_ids: List of contract IDs to analyze (max {MAX_CONTRACTS_TO_ANALYZE} at a time).

        Returns:
            A list of dictionaries, each containing:
            - contract_id
            - contract_name
            - url: The url link of the contract
            - parties
            - summary
            - risks: clause, risk_type, description, likelihood, impact, risk_level, recommendation
            - overall_risk_rating: Low/Medium/High/Critical
            - summary_comment
            - high_risk_clauses
            - next_steps

        Output guidance: Results are in Japanese. Present concise markdown with tables/sections for readability.

        """,
        partial_params={"directory_ids": directory_ids, "conpass_api_service": conpass_api_service},
    )
