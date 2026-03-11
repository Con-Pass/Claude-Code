"""
コンプライアンススコアサービス

契約書の法令適合性をスコア化し、アカウント全体のコンプライアンス状況を集計する。
"""

import os
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.chatbot.tools.risk_analysis.perform_analysis import (
    perform_risk_analysis,
    perform_law_compliance_check,
)
from app.services.chatbot.tools.semantic_search.semantic_search_tool import (
    _get_query_embedding,
    _search_law_regulations,
)

logger = get_logger(__name__)

# スコア計算の減点ポイント
SEVERITY_DEDUCTIONS = {
    "HIGH": 20,
    "MEDIUM": 10,
    "LOW": 5,
}

BASE_SCORE = 100


class ComplianceScoreService:
    """コンプライアンススコア算出サービス"""

    async def calculate_score(
        self,
        contract_id: str,
        contract_body: str,
        directory_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        契約1件のコンプライアンススコアを算出する。

        スコア算出ロジック:
        1. risk_analysis_tool（拡張版）を呼び出し
        2. law_compliance_issues の件数と重要度でスコア計算
           - HIGH issue: -20点
           - MEDIUM issue: -10点
           - LOW issue: -5点
           - 基準点: 100点

        Args:
            contract_id: 契約ID
            contract_body: 契約書本文
            directory_ids: ディレクトリID（オプション）

        Returns:
            {
                "contract_id": str,
                "score": int,
                "issues": list,
                "risk_analysis": dict,
            }
        """
        logger.info(f"Calculating compliance score for contract {contract_id}")

        result: Dict[str, Any] = {
            "contract_id": contract_id,
            "score": BASE_SCORE,
            "issues": [],
            "risk_analysis": None,
        }

        # 1. 通常のリスク分析
        risk_result = await perform_risk_analysis(contract_body)
        if risk_result.status == "success" and risk_result.data:
            result["risk_analysis"] = risk_result.data

        # 2. 法令適合性チェック
        law_issues = await self._get_law_compliance_issues(contract_body)
        result["issues"] = law_issues

        # 3. スコア計算
        score = BASE_SCORE
        for issue in law_issues:
            severity = issue.get("severity", "LOW")
            deduction = SEVERITY_DEDUCTIONS.get(severity, 5)
            score -= deduction

        result["score"] = max(0, score)

        logger.info(
            f"Compliance score for contract {contract_id}: "
            f"{result['score']} ({len(law_issues)} issues found)"
        )

        return result

    async def _get_law_compliance_issues(
        self,
        contract_body: str,
    ) -> List[Dict[str, Any]]:
        """法令適合性の問題を取得する"""
        try:
            query_text = contract_body[:500]
            dense_embedding = await _get_query_embedding(query_text)
            related_laws = await _search_law_regulations(dense_embedding, top_k=5)

            if not related_laws:
                return []

            return await perform_law_compliance_check(contract_body, related_laws)

        except Exception as e:
            logger.warning(f"Law compliance check failed: {e}")
            return []

    async def get_account_summary(
        self,
        account_id: str,
        scores: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        アカウント全体のコンプライアンス状況を集計する。

        Args:
            account_id: アカウントID
            scores: 各契約のスコアリスト

        Returns:
            アカウント全体のサマリー
        """
        total = len(scores)
        if total == 0:
            return {
                "account_id": account_id,
                "total_contracts": 0,
                "average_score": 0.0,
                "score_distribution": {
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                    "critical": 0,
                },
                "contracts_requiring_attention": [],
            }

        # スコア分布の算出
        distribution = {"high": 0, "medium": 0, "low": 0, "critical": 0}
        attention_contracts = []
        total_score = 0.0

        for s in scores:
            score = s.get("score", 0)
            total_score += score

            if score >= 80:
                distribution["high"] += 1
            elif score >= 60:
                distribution["medium"] += 1
            elif score >= 40:
                distribution["low"] += 1
            else:
                distribution["critical"] += 1

            # スコア60以下の契約は要注意
            if score <= 60:
                attention_contracts.append({
                    "contract_id": s.get("contract_id"),
                    "score": score,
                    "issues_count": len(s.get("issues", [])),
                })

        average_score = total_score / total

        return {
            "account_id": account_id,
            "total_contracts": total,
            "average_score": round(average_score, 1),
            "score_distribution": distribution,
            "contracts_requiring_attention": attention_contracts,
        }
