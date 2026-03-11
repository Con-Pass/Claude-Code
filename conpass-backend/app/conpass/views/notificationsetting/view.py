import re
import traceback
from logging import getLogger

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from conpass.views.notificationsetting.serializer.notificationsetting_serializer import \
    NotificationSettingRequestBodySerializer, NotificationSettingResponseBodySerializer
import datetime
from conpass.models import NotificationSetting
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError

logger = getLogger(__name__)


class NotificationSettingView(APIView):
    def get(self, request):
        # query
        notification_setting_data = list(
            NotificationSetting.objects.filter(user_id=self.request.user.id,
                                               status=NotificationSetting.Status.ENABLE.value).all())

        # response
        res_serializer = NotificationSettingResponseBodySerializer(notification_setting_data)
        return Response(data=res_serializer.data)


class NotificationSettingEditView(APIView):
    def post(self, request):
        req_serializer = NotificationSettingRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.error, status=status.HTTP_400_BAD_REQUEST)

        user = self.request.user  # 操作してる人
        datetime_now = make_aware(datetime.datetime.now())
        try:
            for data in req_serializer.data.get('notificationSettingData'):
                if NotificationSetting.objects.filter(user_id=user.id, type=data.get('type'),
                                                      status=NotificationSetting.Status.ENABLE.value).exists():
                    notification_setting = NotificationSetting.objects.filter(user_id=user.id, type=data.get('type'),
                                                                              status=NotificationSetting.Status.ENABLE
                                                                              .value).get()
                else:
                    notification_setting = NotificationSetting()
                    notification_setting.created_by = user
                    notification_setting.created_at = datetime_now

                notification_setting.type = data.get('type')
                notification_setting.name = data.get('name')
                notification_setting.info = data.get('info')
                notification_setting.mail = data.get('mail')
                notification_setting.user = user
                notification_setting.updated_by = user
                notification_setting.updated_at = datetime_now
                notification_setting.save()

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=200)
