import json
from logging import getLogger

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.models import Contract
from conpass.models.gmo_sign import GmoSign
from conpass.services.gmo_sign.gmo_sign_service import GmoSignService
from conpass.views.gmo_sign.serializer.gmo_sign_serializer import (
    GmoSignSerializer,
    GmoSignCreateSerializer,
    GmoSignSendSerializer,
)

logger = getLogger(__name__)


class GmoSignListView(APIView):
    """
    GMO Sign文書一覧
    """

    def get(self, request):
        account_id = request.user.account_id
        queryset = GmoSign.objects.select_related('contract').prefetch_related('signers').filter(
            contract__account_id=account_id,
        ).order_by('-created_at')
        serializer = GmoSignSerializer(queryset, many=True)
        return Response(data={"response": serializer.data})


class GmoSignCreateView(APIView):
    """
    GMO Sign文書作成
    """

    def post(self, request):
        serializer = GmoSignCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            contract = Contract.objects.get(
                pk=serializer.validated_data['contract_id'],
                account_id=request.user.account_id,
            )
        except Contract.DoesNotExist:
            return Response({"msg": ["契約書が見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        service = GmoSignService()
        gmo_sign = service.create_document(
            contract=contract,
            file_data=b'',
            filename=contract.name,
            signers=serializer.validated_data['signers'],
            user=request.user,
        )

        res_serializer = GmoSignSerializer(gmo_sign)
        return Response(data=res_serializer.data, status=status.HTTP_201_CREATED)


class GmoSignSendView(APIView):
    """
    GMO Sign署名依頼送信
    """

    def post(self, request):
        serializer = GmoSignSendSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            gmo_sign = GmoSign.objects.get(
                pk=serializer.validated_data['gmo_sign_id'],
                contract__account_id=request.user.account_id,
            )
        except GmoSign.DoesNotExist:
            return Response({"msg": ["GMO Sign文書が見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        if gmo_sign.status != 'DRAFT':
            return Response(
                {"msg": ["下書き状態の文書のみ送信可能です"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = GmoSignService()
        gmo_sign = service.send_for_signature(gmo_sign)

        res_serializer = GmoSignSerializer(gmo_sign)
        return Response(data=res_serializer.data)


class GmoSignStatusView(APIView):
    """
    GMO Sign文書ステータス取得
    """

    def get(self, request, gmo_sign_id):
        try:
            gmo_sign = GmoSign.objects.get(
                pk=gmo_sign_id,
                contract__account_id=request.user.account_id,
            )
        except GmoSign.DoesNotExist:
            return Response({"msg": ["GMO Sign文書が見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        service = GmoSignService()
        status_data = service.get_status(gmo_sign)

        return Response(data=status_data)


class GmoSignCancelView(APIView):
    """
    GMO Sign署名依頼キャンセル
    """

    def post(self, request, gmo_sign_id):
        try:
            gmo_sign = GmoSign.objects.get(
                pk=gmo_sign_id,
                contract__account_id=request.user.account_id,
            )
        except GmoSign.DoesNotExist:
            return Response({"msg": ["GMO Sign文書が見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        if gmo_sign.status not in ('DRAFT', 'SENT'):
            return Response(
                {"msg": ["キャンセル可能な状態ではありません"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = GmoSignService()
        gmo_sign = service.cancel(gmo_sign)

        res_serializer = GmoSignSerializer(gmo_sign)
        return Response(data=res_serializer.data)


class GmoSignWebhookView(APIView):
    """
    GMO Sign Webhook受信
    """
    permission_classes = [AllowAny]

    def post(self, request):
        signature = request.META.get('HTTP_X_GMO_SIGN_SIGNATURE', '')
        service = GmoSignService()

        if not service.verify_webhook_signature(request.body, signature):
            logger.warning("GMO Sign webhook signature verification failed")
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return Response(
                {"msg": ["不正なリクエストです"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event_type = data.get('event_type', '')
        event_data = data.get('data', {})

        service.handle_webhook_event(event_type, event_data)

        return Response(status=status.HTTP_200_OK)
