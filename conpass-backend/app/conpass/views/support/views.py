import traceback
from logging import getLogger

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.mailer.support_mailer import SupportMailer
from conpass.views.support.serializer.support_request_serializer import SupportRequestRequestBodySerializer
from conpass.models import Support
from conpass.models.constants.statusable import Statusable
import datetime
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError

logger = getLogger(__name__)


class SupportRequestView(APIView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.support_mailer = SupportMailer()

    def post(self, request):
        params = request.data
        req_serializer = SupportRequestRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            support = Support()
            support.name = req_serializer.data.get('name')
            support.body = req_serializer.data.get('body')
            support.type = req_serializer.data.get('type')
            support.status = Statusable.Status.ENABLE.value
            support.created_by_id = self.request.user.id
            support.created_at = make_aware(datetime.datetime.now())
            support.updated_by_id = self.request.user.id
            support.updated_at = make_aware(datetime.datetime.now())
            support.save()

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        self.support_mailer.send_user_request_mail(request.user, support)
        self.support_mailer.send_admin_request_mail(request.user, support)

        return Response(status.HTTP_200_OK)
