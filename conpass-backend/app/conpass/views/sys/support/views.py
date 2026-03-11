import traceback
from logging import getLogger

from rest_framework import status
from rest_framework.response import Response

from conpass.views.sys.common import SysAPIView
from conpass.views.sys.support.serializer.support_list_serializer import SupportListRequestBodySerializer, \
    SupportListResponseBodySerializer
from conpass.views.sys.support.serializer.support_detail_serializer import SupportDetailRequestBodySerializer, \
    SupportDetailResponseBodySerializer, SupportDetailEditRequestBodySerializer
from conpass.models import Support
import datetime
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError

logger = getLogger(__name__)


class SysSupportListView(SysAPIView):
    """
    システム管理_問い合わせ一覧
    """

    def get(self, request):
        req_serializer = SupportListRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wheres = {}
        if req_serializer.data.get('response'):
            wheres['response__in'] = list(map(int, req_serializer.data.get('response', '').split(',')))

        # query
        support_list = list(Support.objects.filter(**wheres).order_by('-created_at', 'id').all())

        # response
        res_serializer = SupportListResponseBodySerializer(support_list)
        return Response(data=res_serializer.data)


class SysSupportDetailView(SysAPIView):
    """
    システム管理_問い合わせ詳細
    """

    def get(self, request):
        """
        問い合わせ取得
        """
        params = request.query_params
        req_serializer = SupportDetailRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            support = Support.objects.get(pk=req_serializer.data.get('id'))
        except Support.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        res_serializer = SupportDetailResponseBodySerializer(support)
        return Response(data=res_serializer.data)

    def post(self, request):
        """
        問い合わせ更新
        """
        params = request.data
        req_serializer = SupportDetailEditRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            support = Support.objects.get(pk=req_serializer.data.get('id'))
            support.response = req_serializer.data.get('response')
            support.status = req_serializer.data.get('status')
            support.updated_by_id = self.request.user.id
            support.updated_at = make_aware(datetime.datetime.now())
            support.save()
        except Support.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status.HTTP_200_OK)
