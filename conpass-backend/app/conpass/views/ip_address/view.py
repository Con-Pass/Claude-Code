import traceback
from logging import getLogger

from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.models.constants import Statusable
from conpass.services.paginate.paginate import StandardResultsSetPagination
from conpass.views.ip_address.serializer.ip_address_serializer import IpAddressRequestBodySerializer, \
    IpAddressResponseSerializer, IpAddressDeleteRequestBodySerializer
from conpass.views.ip_address.serializer.ip_address_detail_serializer import IpAddressDetailResponseBodySerializer
from conpass.views.ip_address.serializer.ip_address_edit_serializer import IpAddressEditRequestBodySerializer
from conpass.models import IpAddress, User
import datetime
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError

logger = getLogger(__name__)


class CustomResultsSetPagination(StandardResultsSetPagination):
    """
    ページサイズの設定
    """
    page_size = 100  # 1ページあたりの表示件数を100件に設定


class SortIpAddressListView(generics.ListAPIView):
    """
    IPアドレス一覧画面検索処理
    """
    serializer_class = IpAddressResponseSerializer
    pagination_class = CustomResultsSetPagination

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        """
        検索処理追加のためオーバーライド
        """
        req_serializer = IpAddressRequestBodySerializer(data=self.request.query_params)
        req_serializer.is_valid(raise_exception=True)

        account_id = self.request.user.account_id

        wheres = {
            'account_id': account_id,
            'status': Statusable.Status.ENABLE.value,
        }
        if req_serializer.data.get('ipAddress'):
            wheres['ip_address__contains'] = req_serializer.data.get('ipAddress')
        if req_serializer.data.get('remarks'):
            wheres['remarks__contains'] = req_serializer.data.get('remarks')

        queryset = IpAddress.objects.filter(**wheres)
        return queryset


class IpAddressDetailView(APIView):

    def get(self, request):
        ip_address_id = request.query_params.get('id')
        my_account_id = self.request.user.account_id

        wheres = {
            'pk': ip_address_id,
            'account_id': my_account_id
        }
        if ip_address_id:
            try:
                ip_address = IpAddress.objects.get(**wheres)
            except IpAddress.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            ip_address = IpAddress()

        res_serializer = IpAddressDetailResponseBodySerializer(ip_address)
        return Response(data=res_serializer.data)


class IpAddressEditView(APIView):

    def post(self, request):
        req_serializer = IpAddressEditRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        client_addr = get_client_ip(request)  # IPアドレス取得
        registed_my_ip_address = False

        edit_ip_address_id = req_serializer.data.get('id')  # 編集対象（無い時は新規作成）
        user_id = self.request.user.id  # 操作している人
        account_id = self.request.user.account_id

        edit_ip_address = req_serializer.data.get('ip_address')
        edit_ip_address_end = req_serializer.data.get('ip_address_end')
        remarks = req_serializer.data.get('remarks')
        datetime_now = make_aware(datetime.datetime.now())
        ip_addresses = [edit_ip_address]

        if edit_ip_address and edit_ip_address_end and not edit_ip_address_id:
            base_ip = ".".join(edit_ip_address.split(".")[:3]) + "."  # IPアドレスの最後の数値を除いたもの
            last_part = int(edit_ip_address.split('.')[-1])  # IPアドレスの最後の数値
            ip_addresses = [base_ip + str(i) for i in range(int(last_part), int(edit_ip_address_end) + 1)]  # 範囲内のIPアドレスをリスト化
            if client_addr in ip_addresses:
                registed_my_ip_address = True  # 自分のIPアドレスが範囲内にある場合は登録済みとする
        else:
            if edit_ip_address == client_addr:
                registed_my_ip_address = True  # 自分のIPアドレスが範囲内にある場合は登録済みとする

        if not registed_my_ip_address:
            wheres = {
                'ip_address': client_addr,
                'account_id': account_id,
                'status': Statusable.Status.ENABLE.value
            }
            if IpAddress.objects.filter(**wheres).exclude(pk=edit_ip_address_id).count() == 0:
                return Response({"msg": ["あなたのIPアドレスが登録されていません。"]}, status=status.HTTP_400_BAD_REQUEST)

        if ip_addresses:
            for eip in ip_addresses:
                # 重複チェック
                wheres = {
                    'ip_address': eip,
                    'account_id': account_id,
                    'status': Statusable.Status.ENABLE.value
                }
                if IpAddress.objects.exclude(pk=edit_ip_address_id).filter(**wheres).count() > 0:
                    if len(ip_addresses) == 1:
                        return Response({"msg": ["このIPアドレスは既に登録済みです。"]}, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        logger.info("IPアドレス重複：" + eip)
                        continue

                if edit_ip_address_id:
                    try:
                        ip_address = IpAddress.objects.get(pk=edit_ip_address_id, account_id=account_id, status=User.Status.ENABLE.value)
                    except IpAddress.DoesNotExist as e:
                        logger.info(e)
                        return Response({"msg": ["パラメータが不正です。"]}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    ip_address = IpAddress()

                try:
                    ip_address.ip_address = eip
                    ip_address.remarks = remarks
                    ip_address.account_id = account_id
                    if not edit_ip_address_id:
                        ip_address.created_by_id = user_id
                        ip_address.created_at = datetime_now
                    ip_address.updated_by_id = user_id
                    ip_address.updated_at = datetime_now
                    ip_address.save()

                except DatabaseError as e:
                    logger.error(f"{e}: {traceback.format_exc()}")
                    return Response({"msg": ["DBエラーが発生しました。"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({"msg": ["パラメータが不正です。"]}, status=status.HTTP_400_BAD_REQUEST)

        response = Response({'success': True}, status=status.HTTP_200_OK)

        return response


class IpAddressDeleteView(APIView):

    def post(self, request):
        req_serializer = IpAddressDeleteRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = request.data
        user = self.request.user
        result_list = []
        is_my_ipaddress = False
        now = make_aware(datetime.datetime.now())
        client_addr = get_client_ip(request)  # IPアドレス取得

        for delete_id in list(params['ids']):
            try:
                delete_ip_address = IpAddress.objects.get(
                    pk=delete_id,
                    account_id=self.request.user.account_id,
                )
            except IpAddress.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です。"]}, status=status.HTTP_400_BAD_REQUEST)

            if delete_ip_address.ip_address == client_addr:
                logger.info("自IPアドレスの削除不可：" + delete_ip_address.ip_address)
                is_my_ipaddress = True
                continue
            else:
                try:
                    delete_ip_address.status = Statusable.Status.DISABLE.value
                    delete_ip_address.updated_by_id = user.id
                    delete_ip_address.updated_at = now
                    delete_ip_address.save()
                except DatabaseError as e:
                    logger.error(f"{e}: {traceback.format_exc()}")
                    return Response({"msg": ["DBエラーが発生しました。"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                result_list.append(delete_id)

        response = Response({'results': result_list, 'is_my_ipaddress': is_my_ipaddress}, status=status.HTTP_200_OK)

        return response


class IpAddressGetView(APIView):

    def get(self, request):
        client_addr = get_client_ip(request)  # IPアドレス取得

        return Response({'ip_address': client_addr}, status=status.HTTP_200_OK)


def get_client_ip(request):
    """
    IPアドレスを取得する
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]  # X-Forwarded-For ヘッダーが使用されている場合（プロキシ経由の場合など）
    else:
        ip = request.META.get('REMOTE_ADDR')  # X-Forwarded-For ヘッダーが存在しない場合
    return ip
