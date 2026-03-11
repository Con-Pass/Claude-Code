import traceback
from logging import getLogger

from rest_framework import status
from rest_framework.response import Response
from conpass.views.sys.bpo.serializer.bpo_list_serializer import BpoListRequestBodySerializer, \
    BpoListResponseBodySerializer, BpoCorrectionListRequestBodySerializer, \
    BpoCorrectionListResponseBodySerializer
from conpass.views.sys.bpo.serializer.bpo_detail_serializer import BpoDetailRequestBodySerializer, \
    BpoDetailResponseBodySerializer, BpoDetailEditRequestBodySerializer, \
    BpoCorrectionDetailRequestBodySerializer, BpoCorrectionDetailEditRequestBodySerializer, \
    BpoCorrectionDetailResponseBodySerializer
from conpass.models import BPORequest, CorrectionRequest
import datetime
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError

from conpass.views.sys.common import SysAPIView

logger = getLogger(__name__)


class SysBpoListView(SysAPIView):
    """
    システム管理_BPO依頼一覧
    """

    def get(self, request):
        req_serializer = BpoListRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wheres = {}
        if req_serializer.data.get('response'):
            wheres['response__in'] = list(map(int, req_serializer.data.get('response', '').split(',')))

        # query
        bpo_list = list(BPORequest.objects.filter(**wheres).order_by('-created_at', 'id').all())

        # response
        res_serializer = BpoListResponseBodySerializer(bpo_list)
        return Response(data=res_serializer.data)


class SysBpoDetailView(SysAPIView):
    """
    システム管理_BPO詳細
    """

    def get(self, request):
        """
        BPO依頼取得
        """
        params = request.query_params
        req_serializer = BpoDetailRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            bpo = BPORequest.objects.get(pk=req_serializer.data.get('id'))
        except BPORequest.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        res_serializer = BpoDetailResponseBodySerializer(bpo)
        return Response(data=res_serializer.data)

    def post(self, request):
        """
        BPO依頼更新
        """
        params = request.data
        req_serializer = BpoDetailEditRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            bpo = BPORequest.objects.get(pk=req_serializer.data.get('id'))
            bpo.response = req_serializer.data.get('response')
            bpo.status = req_serializer.data.get('status')
            bpo.updated_by_id = self.request.user.id
            bpo.updated_at = make_aware(datetime.datetime.now())
            bpo.save()
        except BPORequest.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status.HTTP_200_OK)


class SysBpoCorrectionListView(SysAPIView):
    """
    システム管理_BPOデータ補正依頼一覧
    """

    def get(self, request):
        req_serializer = BpoCorrectionListRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wheres = {}
        if req_serializer.data.get('response'):
            wheres['response__in'] = list(map(int, req_serializer.data.get('response', '').split(',')))

        # query
        bpo_list = list(CorrectionRequest.objects.filter(**wheres).order_by('-created_at', 'id').all())

        # response
        res_serializer = BpoCorrectionListResponseBodySerializer(bpo_list)
        return Response(data=res_serializer.data)


class SysBpoCorrectionDetailView(SysAPIView):
    """
    システム管理_BPOデータ補正詳細
    """

    def get(self, request):
        """
        BPO依頼取得
        """
        params = request.query_params
        req_serializer = BpoCorrectionDetailRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            bpo = CorrectionRequest.objects.get(pk=req_serializer.data.get('id'))
        except CorrectionRequest.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        res_serializer = BpoCorrectionDetailResponseBodySerializer(bpo)
        return Response(data=res_serializer.data)

    def post(self, request):
        """
        BPOデータ補正依頼更新
        """
        params = request.data
        req_serializer = BpoCorrectionDetailEditRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            bpo = CorrectionRequest.objects.get(pk=req_serializer.data.get('id'))
            bpo.response = req_serializer.data.get('response')
            bpo.status = req_serializer.data.get('status')
            bpo.updated_by_id = self.request.user.id
            bpo.updated_at = make_aware(datetime.datetime.now())
            bpo.save()
        except CorrectionRequest.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status.HTTP_200_OK)
