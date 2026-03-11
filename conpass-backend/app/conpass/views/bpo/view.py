import datetime
import traceback
from logging import getLogger

from django.db import transaction
from django.db.utils import DatabaseError
from django.utils.timezone import make_aware
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.mailer.bpo_mailer import BpoMailer
from conpass.mailer.bpo_correction_mailer import BpoCorrectionMailer
from conpass.models import BPORequest, CorrectionRequest, Contract
from conpass.models.constants.statusable import Statusable
from conpass.views.bpo.serializer.bpo_create_serializer import BpoCreateRequestBodySerializer, \
    BpoCorrectionCreateRequestBodySerializer, BpoCorrectionCompleteRequestBodySerializer

logger = getLogger(__name__)


class BpoCreateView(APIView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bpo_mailer = BpoMailer()

    def post(self, request):
        params = request.data
        req_serializer = BpoCreateRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            bpo = BPORequest()
            bpo.name = req_serializer.data.get('name')
            bpo.body = req_serializer.data.get('text')
            bpo.type = req_serializer.data.get('type')
            bpo.status = Statusable.Status.ENABLE.value
            bpo.created_by_id = self.request.user.id
            bpo.created_at = make_aware(datetime.datetime.now())
            bpo.updated_by_id = self.request.user.id
            bpo.updated_at = make_aware(datetime.datetime.now())
            bpo.save()

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        self.bpo_mailer.send_user_request_mail(request.user, bpo)
        self.bpo_mailer.send_admin_request_mail(request.user, bpo)

        return Response(status.HTTP_200_OK)


class BpoCorrectionView(APIView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.correction_mailer = BpoCorrectionMailer()

    def post(self, request):
        params = request.data
        req_serializer = BpoCorrectionCreateRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        contract_ids = req_serializer.data.get('contractIds')
        customer_name = request.user.account.name if request.user.account else ""
        admin_subject = f"【ConPass】データ補正依頼通知 /《{customer_name}》"
        type_display = CorrectionRequest.TYPE_DISPLAYS[CorrectionRequest.Type.CORRECTION.value]
        mail_body = ''

        for contract_id in contract_ids:
            body = f"契約書ID: {contract_id}\n契約書詳細画面: https://www.con-pass.jp/contract/{contract_id}\n"
            mail_body += "\n" + body

            # DBに保存
            with transaction.atomic():
                try:
                    contract = Contract.objects.get(id=contract_id)
                    correction_request = CorrectionRequest()
                    correction_request.name = type_display
                    correction_request.body = body
                    correction_request.contract = contract
                    correction_request.status = Statusable.Status.ENABLE.value
                    correction_request.created_by_id = self.request.user.id
                    correction_request.created_at = make_aware(datetime.datetime.now())
                    correction_request.updated_by_id = self.request.user.id
                    correction_request.updated_at = make_aware(datetime.datetime.now())
                    correction_request.save()
                except DatabaseError as e:
                    logger.error(f"{e}: {traceback.format_exc()}")
                    return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # メール送信
        admin_mail_body = mail_body + f"顧客名： {customer_name}\n依頼者名: {request.user.username}\n依頼者メールアドレス： {request.user.email}\n"
        self.correction_mailer.send_user_request_mail(request.user, type_display, type_display, mail_body)
        self.correction_mailer.send_admin_request_mail(request.user, type_display, admin_subject, admin_mail_body)

        return Response(status.HTTP_200_OK)


class BpoCorrectionCompleteView(APIView):

    def put(self, request):
        params = request.data
        req_serializer = BpoCorrectionCompleteRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        contract_id = req_serializer.data.get('contractId')
        user = self.request.user

        try:
            wheres = {'contract_id': contract_id}
            CorrectionRequest.objects.filter(**wheres).update(
                response=CorrectionRequest.Response.FINISHED.value,
                updated_by_id=user.id,
                updated_at=make_aware(datetime.datetime.now())
            )
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status.HTTP_200_OK)
