"""
契約書メタデータ集計ツール

「今月末が期限の契約は何件？」「今年の自動更新対象の件数は？」
「契約種別ごとの件数を教えて」など、集計クエリに対応する。

ConPass バックエンドの GET /contract/metadata/aggregate を呼び出す。
"""
import logging
from typing import List, Optional

from llama_index.core.tools import FunctionTool

from app.services.conpass_api_service import ConpassApiService

logger = logging.getLogger(__name__)

# LLM が参照するフィールドラベル一覧（ツールの description に含める）
_FIELD_HINT = (
    "contractdate=契約日, contractstartdate=契約開始日, contractenddate=契約終了日, "
    "cancelnotice=解約通知期限, conpass_contract_type=契約種別, "
    "companya=甲会社名, companyb=乙会社名"
)


def get_aggregate_contracts_tool(
    directory_ids: List[int],
    conpass_api_service: ConpassApiService,
) -> FunctionTool:
    async def aggregate_contracts(
        field: str,
        operation: str = "count",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        date_field: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> str:
        """
        契約書のメタデータを集計する（件数・合計・平均）。

        Args:
            field: 集計対象の MetaKey ラベル（例: "contractenddate", "conpass_contract_type"）
            operation: "count"（件数, default）| "sum"（合計）| "avg"（平均）
            date_from: 日付フィルタ開始 YYYY-MM-DD（date_field の日付に適用）
            date_to: 日付フィルタ終了 YYYY-MM-DD
            date_field: 日付フィルタを適用するフィールド（省略時: field と同じ）
            group_by: グループ化する MetaKey ラベル（例: "conpass_contract_type"）
        """
        try:
            params: dict = {
                "field": field,
                "operation": operation,
                "directory_ids": ",".join(str(d) for d in directory_ids),
            }
            if date_from:
                params["date_from"] = date_from
            if date_to:
                params["date_to"] = date_to
            if date_field:
                params["date_field"] = date_field
            if group_by:
                params["group_by"] = group_by

            response = await conpass_api_service._get_data_from_conpass_api(
                "/contract/metadata/aggregate",
                params=params,
            )

            if response.status != "success" or not response.data:
                return "集計データの取得に失敗しました。"

            data = response.data
            total = data.get("total", 0)
            unit = data.get("unit", "")
            groups = data.get("groups", [])

            op_label = {"count": "件数", "sum": "合計", "avg": "平均"}.get(operation, operation)

            # 数値フォーマット
            if isinstance(total, float) and total == int(total):
                total_str = f"{int(total):,}"
            elif isinstance(total, float):
                total_str = f"{total:,.1f}"
            else:
                total_str = f"{total:,}"

            result_lines = [f"**{op_label}: {total_str}{unit}**"]

            if groups:
                result_lines.append("\n**内訳:**")
                for g in groups:
                    g_total = g.get("total", 0)
                    if isinstance(g_total, float) and g_total == int(g_total):
                        g_str = f"{int(g_total):,}"
                    elif isinstance(g_total, float):
                        g_str = f"{g_total:,.1f}"
                    else:
                        g_str = f"{g_total:,}"
                    result_lines.append(f"- {g.get('group', '')}: {g_str}{unit}")

            return "\n".join(result_lines)

        except Exception as e:
            logger.error(f"[AggregateContracts] エラー: {e}", exc_info=True)
            return f"集計中にエラーが発生しました: {e}"

    return FunctionTool.from_defaults(
        async_fn=aggregate_contracts,
        name="aggregate_contracts",
        description=(
            "契約書のメタデータを集計する（件数・合計・平均）。"
            "「今月末が期限の契約は何件？」「今年の自動更新対象の件数は？」"
            "「契約種別ごとの件数を教えて」などの集計クエリに対応。"
            f"field には MetaKey ラベルを指定: {_FIELD_HINT}。"
            "date_from/date_to で日付範囲を指定（YYYY-MM-DD形式）。"
            "group_by でグループ化（例: group_by='conpass_contract_type'）。"
        ),
    )
