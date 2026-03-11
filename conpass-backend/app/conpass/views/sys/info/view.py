import datetime
import traceback
from logging import getLogger

import pytz
from django.db.utils import DatabaseError
from django.utils.timezone import make_aware
from rest_framework import status
from rest_framework.response import Response

from conpass.models import Information
from conpass.views.sys.common import SysAPIView
from conpass.views.sys.info.serializer.info_detail_serializer import InfoDetailRequestBodySerializer, \
    InfoDetailResponseBodySerializer
from conpass.views.sys.info.serializer.info_edit_serializer import InfoEditResponseBodySerializer, \
    InfoEditRequestBodySerializer, InfoEditGetRequestBodySerializer
from conpass.views.sys.info.serializer.info_list_serializer import InfoListRequestBodySerializer, \
    InfoListResponseBodySerializer

logger = getLogger(__name__)
tz = pytz.timezone('Asia/Tokyo')


class SysInfoListView(SysAPIView):
    """
    システム管理_お知らせ一覧
    """
    def get(self, request):
        req_serializer = InfoListRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wheres = {}
        if req_serializer.data.get('status'):
            wheres['status'] = req_serializer.data.get('status')

        orders = []
        odr_start = req_serializer.data.get('orderByStartAt')
        if odr_start:
            orders.append('{}start_at'.format('-' if odr_start == 'DESC' else ''))
        odr_order = req_serializer.data.get('orderByOrder')
        if odr_order:
            orders.append('{}order'.format('-' if odr_order == 'DESC' else ''))
        orders.append('id')
        info_list = list(Information.objects.filter(**wheres).order_by(*orders).all())

        # response
        res_serializer = InfoListResponseBodySerializer(info_list)
        return Response(data=res_serializer.data)


class SysInfoDetailView(SysAPIView):
    """
    システム管理_お知らせ詳細
    """
    def get(self, request):
        """
        お知らせ取得
        """
        params = request.query_params
        req_serializer = InfoDetailRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            info = Information.objects.get(pk=req_serializer.data.get('id'))
        except Information.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        res_serializer = InfoDetailResponseBodySerializer(info)
        return Response(data=res_serializer.data)


class SysInfoEditView(SysAPIView):
    """
    システム管理_お知らせ修正
    """
    def get(self, request):
        """
        お知らせ取得
        """
        params = request.query_params
        req_serializer = InfoEditGetRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            info = Information.objects.get(pk=req_serializer.data.get('id'))
            # awareの日時を日本時間に直して分割
            n_start_at = info.start_at.astimezone(tz).replace(tzinfo=None)
            info.start_date = n_start_at.date()
            info.start_time = n_start_at.time()
            n_end_at = info.end_at.astimezone(tz).replace(tzinfo=None)
            info.end_date = n_end_at.date()
            info.end_time = n_end_at.time()
        except Information.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        res_serializer = InfoEditResponseBodySerializer(info)
        return Response(data=res_serializer.data)

    def post(self, request):
        """
        お知らせ修正・作成実行
        """
        params = request.data
        req_serializer = InfoEditRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            if req_serializer.data.get('id'):
                info = Information.objects.get(pk=req_serializer.data.get('id'))
            else:
                # 新規作成の場合
                info = Information()
                info.created_at = make_aware(datetime.datetime.now())
                info.created_by_id = self.request.user.id

            info.title = req_serializer.data.get('title')
            info.body = req_serializer.data.get('body')
            info.url = req_serializer.data.get('url')
            info.order = req_serializer.data.get('order')
            info.start_at = make_aware(datetime.datetime.strptime(
                req_serializer.data.get('startDate') + ' ' + req_serializer.data.get('startTime'), '%Y-%m-%d %H:%M:%S'))
            info.end_at = make_aware(datetime.datetime.strptime(
                req_serializer.data.get('endDate') + ' ' + req_serializer.data.get('endTime'), '%Y-%m-%d %H:%M:%S'))
            info.status = req_serializer.data.get('status')
            info.updated_by_id = self.request.user.id
            info.updated_at = make_aware(datetime.datetime.now())
            info.save()
        except Information.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status.HTTP_200_OK)
