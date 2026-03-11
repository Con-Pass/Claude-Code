"""
コンプライアンス照会ツール（オーケストレーター用）

チャットからコンプライアンス状況を照会するためのツール。
オーケストレーターが直接呼び出し、サブエージェントへのルーティング不要。
"""
from typing import Any, Dict, Optional

from llama_index.core.tools import FunctionTool

from app.core.logging_config import get_logger

logger = get_logger(__name__)


async def get_compliance_summary(account_id: str) -> Dict[str, Any]:
    """
    アカウント全体のコンプライアンス状況サマリーを取得する。

    Args:
        account_id: アカウントID

    Returns:
        コンプライアンスサマリー情報
    """
    try:
        from app.services.compliance.compliance_score_service import ComplianceScoreService

        service = ComplianceScoreService()
        # プロトタイプ: キャッシュ済みスコアなし（TODO: Firestoreから取得）
        result = await service.get_account_summary(account_id=account_id, scores=[])
        return result
    except Exception as e:
        logger.exception(f"Error getting compliance summary: {e}")
        return {
            "account_id": account_id,
            "error": "コンプライアンスサマリーの取得に失敗しました",
        }


async def check_contract_compliance(contract_id: str, contract_body: str) -> Dict[str, Any]:
    """
    特定契約書のコンプライアンススコアを算出する。

    Args:
        contract_id: 契約ID
        contract_body: 契約書本文（先頭2000文字以内）

    Returns:
        コンプライアンススコアと法令適合性の問題リスト
    """
    try:
        from app.services.compliance.compliance_score_service import ComplianceScoreService

        service = ComplianceScoreService()
        result = await service.calculate_score(
            contract_id=contract_id,
            contract_body=contract_body,
        )
        return result
    except Exception as e:
        logger.exception(f"Error checking contract compliance: {e}")
        return {
            "contract_id": contract_id,
            "score": None,
            "error": "コンプライアンスチェックに失敗しました",
        }


def get_compliance_summary_tool() -> FunctionTool:
    """アカウントコンプライアンスサマリーツール"""
    return FunctionTool.from_defaults(
        async_fn=get_compliance_summary,
        name="get_compliance_summary",
        description="""
        アカウント全体のコンプライアンス状況サマリーを取得する。

        使用シーン:
        - ユーザーが「コンプライアンス状況を教えて」「法令適合性の概要は？」と質問した場合
        - コンプライアンスダッシュボードの概要情報が必要な場合

        引数:
            account_id: アカウントID（ユーザーのアカウントIDを使用）

        返却値:
        - total_contracts: 契約総数
        - average_score: 平均コンプライアンススコア (0-100)
        - score_distribution: スコア分布 (high: 80+, medium: 60-79, low: 40-59, critical: <40)
        - contracts_requiring_attention: 要注意契約リスト（スコア60以下）
        """,
    )


def get_contract_compliance_tool() -> FunctionTool:
    """契約書コンプライアンスチェックツール"""
    return FunctionTool.from_defaults(
        async_fn=check_contract_compliance,
        name="check_contract_compliance",
        description="""
        特定の契約書のコンプライアンススコア（0-100）を算出し、法令適合性の問題を特定する。

        使用シーン:
        - ユーザーが特定の契約のコンプライアンス状態を知りたい場合
        - 「この契約は法令に適合しているか？」「コンプライアンススコアは？」などの質問

        引数:
            contract_id: 契約ID
            contract_body: 契約書本文（長い場合は先頭2000文字を使用）

        返却値:
        - contract_id: 契約ID
        - score: コンプライアンススコア (0-100, 高いほど良い)
        - issues: 法令適合性の問題リスト (severity: HIGH/MEDIUM/LOW, description)

        スコア算出ロジック:
        - 基準点: 100点
        - HIGH issue: -20点
        - MEDIUM issue: -10点
        - LOW issue: -5点
        """,
    )
