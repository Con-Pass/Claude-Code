import traceback
from logging import getLogger

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from conpass.views.dashboard.serializer.dashboard_info_list_serializer import DashboardInfoListResponseBodySerializer
from conpass.models import Information
from conpass.models.constants.statusable import Statusable
import datetime
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError

logger = getLogger(__name__)


class DashboardInfoListView(APIView):
    def get(self, request):
        try:
            now = make_aware(datetime.datetime.now())
            info_list = Information.objects.filter(status=Statusable.Status.ENABLE.value,
                                                   start_at__lte=now,
                                                   end_at__gt=now).order_by('-order', '-start_at').all()[:5]

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        res_serializer = DashboardInfoListResponseBodySerializer(info_list)
        return Response(data=res_serializer.data)
