"""
契約書メタデータ集計 API

GET /api/contract/metadata/aggregate
  件数・合計・平均を返す。日付範囲・ディレクトリフィルタ・グループ化に対応。

クエリパラメータ:
  field        str  MetaKey ラベル（必須）。例: "contractenddate", "amount"
  operation    str  "count"(件数, default) | "sum"(合計) | "avg"(平均)
  date_from    str  日付フィルタ開始 (YYYY-MM-DD)。date_field の date_value に適用
  date_to      str  日付フィルタ終了 (YYYY-MM-DD)
  date_field   str  日付フィルタを適用するフィールド（省略時: field と同じ）
  directory_ids str カンマ区切りのディレクトリID（省略時: 許可ディレクトリ全件）
  group_by     str  グループ化する MetaKey ラベル（省略時: グループ化なし）

レスポンス:
  {
    "total":     42,         // 件数・合計・平均
    "unit":      "件",       // count=件, sum/avg=空文字
    "operation": "count",
    "field":     "contractenddate",
    "groups": [              // group_by 指定時のみ
      {"group": "秘密保持契約", "total": 10},
      ...
    ]
  }
"""
import logging

from django.db.models import Avg, Count, FloatField, Sum
from django.db.models.functions import Cast
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.models.constants import ContractTypeable
from conpass.models.meta_data import MetaData
from conpass.services.directory.directory_service import DirectoryService

logger = logging.getLogger(__name__)


class ContractMetaAggregateView(APIView):
    """契約書メタデータ集計 API"""

    def get(self, request):
        field = request.GET.get("field", "").strip()
        operation = request.GET.get("operation", "count").lower()
        date_from = request.GET.get("date_from", "").strip() or None
        date_to = request.GET.get("date_to", "").strip() or None
        date_field_label = request.GET.get("date_field", "").strip() or field
        directory_ids_str = request.GET.get("directory_ids", "").strip()
        group_by_label = request.GET.get("group_by", "").strip() or None

        if not field:
            return Response({"error": "field パラメータは必須です"}, status=400)

        if operation not in ("count", "sum", "avg"):
            return Response({"error": "operation は count|sum|avg のいずれかを指定してください"}, status=400)

        # ── ディレクトリ権限チェック ──────────────────────────────────
        allowed_dirs = DirectoryService().get_allowed_directories(
            request.user, ContractTypeable.ContractType.CONTRACT.value
        )
        allowed_dir_ids = {d.id for d in allowed_dirs}

        if directory_ids_str:
            requested_ids = {
                int(x) for x in directory_ids_str.split(",") if x.strip().isdigit()
            }
            dir_ids = list(allowed_dir_ids & requested_ids)
        else:
            dir_ids = list(allowed_dir_ids)

        if not dir_ids:
            return Response({"total": 0, "unit": "件", "operation": operation, "field": field, "groups": []})

        # ── 日付フィルタで対象 contract_id を取得 ────────────────────
        contract_id_filter = None
        if date_from or date_to:
            date_qs = MetaData.objects.filter(
                key__label=date_field_label,
                status=1,
                contract__is_garbage=False,
                contract__directory_id__in=dir_ids,
                contract__type=ContractTypeable.ContractType.CONTRACT.value,
            )
            if date_from:
                date_qs = date_qs.filter(date_value__gte=date_from)
            if date_to:
                date_qs = date_qs.filter(date_value__lte=date_to)
            contract_id_filter = list(date_qs.values_list("contract_id", flat=True).distinct())

            if not contract_id_filter:
                return Response({
                    "total": 0, "unit": "件", "operation": operation,
                    "field": field, "groups": []
                })

        # ── 集計ベースクエリ ─────────────────────────────────────────
        qs = MetaData.objects.filter(
            key__label=field,
            status=1,
            contract__is_garbage=False,
            contract__directory_id__in=dir_ids,
            contract__type=ContractTypeable.ContractType.CONTRACT.value,
        )
        if contract_id_filter is not None:
            qs = qs.filter(contract_id__in=contract_id_filter)

        # ── 集計実行 ─────────────────────────────────────────────────
        if operation == "sum":
            numeric_qs = qs.annotate(numeric_val=Cast("value", output_field=FloatField()))
            total = numeric_qs.aggregate(total=Sum("numeric_val"))["total"] or 0.0
            unit = ""
        elif operation == "avg":
            numeric_qs = qs.annotate(numeric_val=Cast("value", output_field=FloatField()))
            total = numeric_qs.aggregate(avg=Avg("numeric_val"))["avg"] or 0.0
            unit = ""
        else:  # count
            total = qs.values("contract_id").distinct().count()
            unit = "件"

        # ── グループ別集計 ───────────────────────────────────────────
        groups = []
        if group_by_label:
            # field が存在する contract_id に絞る
            field_contract_ids = list(qs.values_list("contract_id", flat=True).distinct())

            group_qs = MetaData.objects.filter(
                key__label=group_by_label,
                status=1,
                contract__is_garbage=False,
                contract__directory_id__in=dir_ids,
                contract__type=ContractTypeable.ContractType.CONTRACT.value,
                contract_id__in=field_contract_ids,
            ).values("value").annotate(cnt=Count("contract_id", distinct=True)).order_by("-cnt")

            groups = [
                {"group": row["value"] or "（未設定）", "total": row["cnt"]}
                for row in group_qs
            ]

        logger.info(
            f"[AggregateView] field={field} op={operation} date={date_from}~{date_to} "
            f"dirs={len(dir_ids)} total={total}"
        )

        return Response({
            "total": total,
            "unit": unit,
            "operation": operation,
            "field": field,
            "groups": groups,
        })
