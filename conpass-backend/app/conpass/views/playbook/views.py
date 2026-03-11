from logging import getLogger

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.models.playbook import (
    PlaybookTemplate,
    TenantPlaybook,
    ClausePolicy,
    TenantRuleSet,
    TenantRule,
    RuleEvaluationLog,
    ResponseTemplate,
)
from conpass.services.playbook.playbook_service import PlaybookService
from conpass.views.playbook.serializer.playbook_serializer import (
    PlaybookTemplateSerializer,
    TenantPlaybookListSerializer,
    TenantPlaybookCreateSerializer,
    TenantPlaybookUpdateSerializer,
    ApplyTemplateSerializer,
    ClausePolicySerializer,
    ClausePolicyCreateSerializer,
    ClausePolicyUpdateSerializer,
    TenantRuleSerializer,
    TenantRuleCreateSerializer,
    TenantRuleUpdateSerializer,
    RuleEvaluationLogSerializer,
    ResponseTemplateSerializer,
    ResponseTemplateCreateSerializer,
    ResponseTemplateUpdateSerializer,
)

logger = getLogger(__name__)


# --- PlaybookTemplate ---

class PlaybookTemplateListView(APIView):
    """
    プレイブックテンプレート一覧（業種別フィルタ対応）
    """

    def get(self, request):
        queryset = PlaybookTemplate.objects.all().order_by('-created_at')
        industry = request.query_params.get('industry')
        if industry:
            queryset = queryset.filter(industry=industry)
        serializer = PlaybookTemplateSerializer(queryset, many=True)
        return Response(data={"response": serializer.data})


# --- TenantPlaybook ---

class TenantPlaybookListView(APIView):
    """
    テナントPlaybook一覧取得
    """

    def get(self, request):
        account_id = request.user.account_id
        queryset = TenantPlaybook.objects.select_related('template').filter(
            account_id=account_id,
        ).order_by('-created_at')
        serializer = TenantPlaybookListSerializer(queryset, many=True)
        return Response(data={"response": serializer.data})


class TenantPlaybookCreateView(APIView):
    """
    テナントPlaybook作成
    """

    def post(self, request):
        serializer = TenantPlaybookCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        playbook = TenantPlaybook.objects.create(
            account_id=request.user.account_id,
            **serializer.validated_data,
        )
        res_serializer = TenantPlaybookListSerializer(playbook)
        return Response(data=res_serializer.data, status=status.HTTP_201_CREATED)


class TenantPlaybookUpdateView(APIView):
    """
    テナントPlaybook更新
    """

    def put(self, request, playbook_id):
        try:
            playbook = TenantPlaybook.objects.get(
                pk=playbook_id, account_id=request.user.account_id,
            )
        except TenantPlaybook.DoesNotExist:
            return Response({"msg": ["プレイブックが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        serializer = TenantPlaybookUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        for key, value in serializer.validated_data.items():
            setattr(playbook, key, value)
        playbook.save()

        res_serializer = TenantPlaybookListSerializer(playbook)
        return Response(data=res_serializer.data)


class TenantPlaybookDeleteView(APIView):
    """
    テナントPlaybook削除
    """

    def delete(self, request, playbook_id):
        try:
            playbook = TenantPlaybook.objects.get(
                pk=playbook_id, account_id=request.user.account_id,
            )
        except TenantPlaybook.DoesNotExist:
            return Response({"msg": ["プレイブックが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        playbook.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TenantPlaybookApplyTemplateView(APIView):
    """
    テンプレート適用（ClausePolicyを一括生成）
    """

    def post(self, request, playbook_id):
        try:
            playbook = TenantPlaybook.objects.get(
                pk=playbook_id, account_id=request.user.account_id,
            )
        except TenantPlaybook.DoesNotExist:
            return Response({"msg": ["プレイブックが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        serializer = ApplyTemplateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            template = PlaybookTemplate.objects.get(pk=serializer.validated_data['template_id'])
        except PlaybookTemplate.DoesNotExist:
            return Response({"msg": ["テンプレートが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        created = PlaybookService.apply_template(playbook, template)
        clauses = ClausePolicy.objects.filter(playbook=playbook)
        clause_serializer = ClausePolicySerializer(clauses, many=True)
        return Response(data={
            "created_count": len(created),
            "clauses": clause_serializer.data,
        })


# --- ClausePolicy ---

class ClausePolicyListView(APIView):
    """
    条項ポリシー一覧・作成
    """

    def get(self, request, playbook_id):
        try:
            playbook = TenantPlaybook.objects.get(
                pk=playbook_id, account_id=request.user.account_id,
            )
        except TenantPlaybook.DoesNotExist:
            return Response({"msg": ["プレイブックが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        queryset = ClausePolicy.objects.filter(playbook=playbook).order_by('clause_type')
        serializer = ClausePolicySerializer(queryset, many=True)
        return Response(data={"response": serializer.data})

    def post(self, request, playbook_id):
        try:
            playbook = TenantPlaybook.objects.get(
                pk=playbook_id, account_id=request.user.account_id,
            )
        except TenantPlaybook.DoesNotExist:
            return Response({"msg": ["プレイブックが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClausePolicyCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # unique_together制約チェック
        if ClausePolicy.objects.filter(
            playbook=playbook, clause_type=serializer.validated_data['clause_type']
        ).exists():
            return Response(
                {"msg": ["この条項タイプは既に登録されています"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        clause = ClausePolicy.objects.create(playbook=playbook, **serializer.validated_data)
        res_serializer = ClausePolicySerializer(clause)
        return Response(data=res_serializer.data, status=status.HTTP_201_CREATED)


class ClausePolicyDetailView(APIView):
    """
    条項ポリシー更新・削除
    """

    def put(self, request, playbook_id, clause_id):
        try:
            playbook = TenantPlaybook.objects.get(
                pk=playbook_id, account_id=request.user.account_id,
            )
        except TenantPlaybook.DoesNotExist:
            return Response({"msg": ["プレイブックが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        try:
            clause = ClausePolicy.objects.get(pk=clause_id, playbook=playbook)
        except ClausePolicy.DoesNotExist:
            return Response({"msg": ["条項ポリシーが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClausePolicyUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        for key, value in serializer.validated_data.items():
            setattr(clause, key, value)
        clause.save()

        res_serializer = ClausePolicySerializer(clause)
        return Response(data=res_serializer.data)

    def delete(self, request, playbook_id, clause_id):
        try:
            playbook = TenantPlaybook.objects.get(
                pk=playbook_id, account_id=request.user.account_id,
            )
        except TenantPlaybook.DoesNotExist:
            return Response({"msg": ["プレイブックが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        try:
            clause = ClausePolicy.objects.get(pk=clause_id, playbook=playbook)
        except ClausePolicy.DoesNotExist:
            return Response({"msg": ["条項ポリシーが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        clause.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- TenantRule ---

class TenantRuleListView(APIView):
    """
    ルール一覧・作成
    """

    def get(self, request):
        account_id = request.user.account_id
        queryset = TenantRule.objects.select_related('rule_set').filter(
            rule_set__account_id=account_id,
        ).order_by('-created_at')

        rule_type = request.query_params.get('rule_type')
        if rule_type:
            queryset = queryset.filter(rule_type=rule_type)

        severity = request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)

        serializer = TenantRuleSerializer(queryset, many=True)
        return Response(data={"response": serializer.data})

    def post(self, request):
        serializer = TenantRuleCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # rule_setがリクエストユーザーのアカウントに属するかチェック
        rule_set = serializer.validated_data.get('rule_set')
        if rule_set.account_id != request.user.account_id:
            return Response({"msg": ["権限がありません"]}, status=status.HTTP_403_FORBIDDEN)

        rule = TenantRule.objects.create(**serializer.validated_data)
        res_serializer = TenantRuleSerializer(rule)
        return Response(data=res_serializer.data, status=status.HTTP_201_CREATED)


class TenantRuleDetailView(APIView):
    """
    ルール更新・削除
    """

    def put(self, request, rule_id):
        try:
            rule = TenantRule.objects.select_related('rule_set').get(
                pk=rule_id, rule_set__account_id=request.user.account_id,
            )
        except TenantRule.DoesNotExist:
            return Response({"msg": ["ルールが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        serializer = TenantRuleUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        for key, value in serializer.validated_data.items():
            setattr(rule, key, value)
        rule.save()

        res_serializer = TenantRuleSerializer(rule)
        return Response(data=res_serializer.data)

    def delete(self, request, rule_id):
        try:
            rule = TenantRule.objects.get(
                pk=rule_id, rule_set__account_id=request.user.account_id,
            )
        except TenantRule.DoesNotExist:
            return Response({"msg": ["ルールが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        rule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TenantRuleAlertsView(APIView):
    """
    現在発生中のアラート一覧（RuleEvaluationLog[WARN/FAIL]）
    """

    def get(self, request):
        account_id = request.user.account_id
        queryset = RuleEvaluationLog.objects.select_related('rule', 'contract').filter(
            rule__rule_set__account_id=account_id,
            result__in=['WARN', 'FAIL'],
        ).order_by('-evaluated_at')

        serializer = RuleEvaluationLogSerializer(queryset, many=True)
        return Response(data={"response": serializer.data})


# --- ResponseTemplate ---

class ResponseTemplateListView(APIView):
    """
    回答テンプレート一覧・作成
    """

    def get(self, request):
        account_id = request.user.account_id
        queryset = ResponseTemplate.objects.prefetch_related('variables').filter(
            account_id=account_id,
        ).order_by('-created_at')

        inquiry_type = request.query_params.get('inquiry_type')
        if inquiry_type:
            queryset = queryset.filter(inquiry_type=inquiry_type)

        serializer = ResponseTemplateSerializer(queryset, many=True)
        return Response(data={"response": serializer.data})

    def post(self, request):
        serializer = ResponseTemplateCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        template = PlaybookService.create_response_template_with_variables(
            account=request.user.account,
            data=serializer.validated_data,
        )
        res_serializer = ResponseTemplateSerializer(template)
        return Response(data=res_serializer.data, status=status.HTTP_201_CREATED)


class ResponseTemplateDetailView(APIView):
    """
    回答テンプレート更新・削除
    """

    def put(self, request, template_id):
        try:
            template = ResponseTemplate.objects.get(
                pk=template_id, account_id=request.user.account_id,
            )
        except ResponseTemplate.DoesNotExist:
            return Response({"msg": ["テンプレートが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        serializer = ResponseTemplateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        template = PlaybookService.update_response_template_with_variables(
            template=template,
            data=serializer.validated_data,
        )
        res_serializer = ResponseTemplateSerializer(template)
        return Response(data=res_serializer.data)

    def delete(self, request, template_id):
        try:
            template = ResponseTemplate.objects.get(
                pk=template_id, account_id=request.user.account_id,
            )
        except ResponseTemplate.DoesNotExist:
            return Response({"msg": ["テンプレートが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        template.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
