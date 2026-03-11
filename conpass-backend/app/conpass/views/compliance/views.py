from logging import getLogger

from django.db.models import Count
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.models.playbook import (
    TenantRule,
    RuleEvaluationLog,
)
from conpass.tasks import evaluate_tenant_rules_for_account

logger = getLogger(__name__)


class ComplianceRescoreView(APIView):
    """
    POST /api/v1/compliance/rescore/
    全契約に対してテナントルールを再評価するCeleryタスクをキューイングする。
    """

    def post(self, request):
        account = request.user.account
        evaluate_tenant_rules_for_account.delay(account.id)
        logger.info(
            "Compliance rescore queued for account_id=%s by user_id=%s",
            account.id, request.user.id,
        )
        return Response({
            "status": "queued",
            "account_id": account.id,
        })


class LawChangeHookView(APIView):
    """
    POST /api/v1/compliance/law-change-hook/
    BE3のCloud Scheduler（e-Gov改正検知）から呼ばれる内部エンドポイント。
    改正された法令に関連するAccountを洗い出してCeleryタスクを投入する。
    認証はIPホワイトリスト等の外部保護に委ねる。
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        law_id = request.data.get('law_id')
        law_name = request.data.get('law_name')

        if not law_id and not law_name:
            return Response(
                {"msg": ["law_id または law_name が必要です"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # LAW_UPDATE ルールを持つ全アクティブアカウントに再評価をトリガー
        rules = TenantRule.objects.select_related('rule_set').filter(
            rule_type='LAW_UPDATE',
            is_active=True,
        )

        triggered_account_ids = set()
        for rule in rules:
            account_id = rule.rule_set.account_id
            if account_id not in triggered_account_ids:
                evaluate_tenant_rules_for_account.delay(account_id)
                triggered_account_ids.add(account_id)

        logger.info(
            "Law change hook triggered: law_id=%s, law_name=%s, affected_accounts=%d",
            law_id, law_name, len(triggered_account_ids),
        )

        return Response({
            "status": "triggered",
            "law_id": law_id,
            "law_name": law_name,
            "affected_accounts": len(triggered_account_ids),
        })


class ComplianceScoreSummaryView(APIView):
    """
    GET /api/v1/compliance/score-summary/
    アカウントのコンプライアンス状況サマリーを返す（フロントエンド用）。
    """

    def get(self, request):
        account_id = request.user.account_id

        logs = RuleEvaluationLog.objects.select_related(
            'rule', 'contract',
        ).filter(
            rule__rule_set__account_id=account_id,
        )

        total_count = logs.count()
        pass_count = logs.filter(result='PASS').count()
        warn_count = logs.filter(result='WARN').count()
        fail_count = logs.filter(result='FAIL').count()

        # 重大度分布
        severity_distribution = {}
        severity_qs = logs.filter(
            result__in=['WARN', 'FAIL'],
        ).values('rule__severity').annotate(count=Count('id'))
        for entry in severity_qs:
            severity_distribution[entry['rule__severity']] = entry['count']

        # 最新アラート（WARN/FAIL、最新20件）
        recent_alerts = []
        recent_logs = logs.filter(
            result__in=['WARN', 'FAIL'],
        ).order_by('-evaluated_at')[:20]

        for log in recent_logs:
            recent_alerts.append({
                'id': log.id,
                'rule_name': log.rule.name,
                'rule_type': log.rule.rule_type,
                'severity': log.rule.severity,
                'result': log.result,
                'contract_id': log.contract_id,
                'contract_name': getattr(log.contract, 'name', ''),
                'evaluated_at': log.evaluated_at.isoformat() if log.evaluated_at else None,
                'detail': log.detail,
            })

        # コンプライアンススコア（100点満点）
        if total_count > 0:
            score = round((pass_count / total_count) * 100, 1)
        else:
            score = 100.0  # 評価対象なしは満点とする

        return Response({
            "account_id": account_id,
            "compliance_score": score,
            "total_evaluations": total_count,
            "pass_count": pass_count,
            "warn_count": warn_count,
            "fail_count": fail_count,
            "severity_distribution": severity_distribution,
            "recent_alerts": recent_alerts,
        })
