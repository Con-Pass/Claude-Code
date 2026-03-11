import copy
from logging import getLogger
from typing import Union

from django.http import HttpRequest
from rest_framework import generics
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.services.client.client_csv_importer import ClientCsvImporter
from conpass.services.paginate.paginate import StandardResultsSetPagination
from conpass.views.client.serializer.client_serializer import ClientRequestBodySerializer, \
    ClientResponseBodySerializer, ClientDeleteRequestBodySerializer, ClientResponseSerializer, \
    ClientDataResponseBodySerializer
from conpass.views.client.serializer.client_edit_serializer import ClientEditPostRequestBodySerializer, \
    ClientEditResponseBodySerializer, ClientEditGetRequestBodySerializer
from conpass.views.client.serializer.client_detail_serializer import ClientDetailRequestBodySerializer, \
    ClientDetailResponseBodySerializer
from conpass.models import Client, User, Corporate
from django.db.models import Prefetch, Exists, OuterRef
from collections import OrderedDict
import datetime
from django.utils.timezone import make_aware

logger = getLogger(__name__)


class SortClientListView(generics.ListAPIView):
    """
    連絡先一覧画面検索処理
    """
    serializer_class = ClientResponseSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        検索処理追加のためオーバーライド
        """
        queryset = Client.objects.select_related('corporate').filter(
            provider_account=self.request.user.account_id,
            status=Client.Status.ENABLE.value,
        )
        # 絞り込み
        if corporate_name := self.request.query_params.get('corporateName'):
            queryset = queryset.filter(corporate__name__icontains=corporate_name)
        if user_name := self.request.query_params.get('userName'):
            queryset = queryset.filter(
                Exists(User.objects.filter(
                    username__icontains=user_name,
                    client=OuterRef('pk'),
                ))
            )

        return queryset


class ClientListView(APIView):

    def get(self, request):
        """
        入力チェックを追加
        """
        req_serializer = ClientRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # query
        user = self.request.user
        client = Client
        wheres = {
            'provider_account': user.account_id,
            'status': Client.Status.ENABLE.value,
        }
        user_wheres = {
            'status': User.Status.ENABLE.value,
        }

        if request.query_params.get('corporateName'):
            wheres['corporate__name__contains'] = request.GET.get('corporateName')
        if request.query_params.get('userName'):
            wheres['user_client__username__contains'] = request.GET.get('userName')
            user_wheres['name__contains'] = request.GET.get('userName')

        clients = client.objects.select_related('corporate').filter(**wheres).all() \
            .prefetch_related(Prefetch('user_client', queryset=User.objects.filter(**user_wheres).all()))

        result_list = []
        for c in clients:
            # 連絡先に紐づく利用者ごとに行を作成
            usr_list = c.user_client.all()
            if len(usr_list):
                for usr in usr_list:
                    row_data = {
                        'id': c.id,
                        'name': c.name,
                        'corporate': c.corporate,
                        'created_at': c.created_at,
                        'created_by': c.created_by,
                        'updated_at': c.updated_at,
                        'updated_by': c.updated_by,
                        'user': usr
                    }
                    result_list.append(row_data)

            else:
                row_data = {
                    'id': c.id,
                    'name': c.name,
                    'corporate': c.corporate,
                    'created_at': c.created_at,
                    'created_by': c.created_by,
                    'updated_at': c.updated_at,
                    'updated_by': c.updated_by,
                    'user': User()
                }
                result_list.append(row_data)

        # response
        res_serializer = ClientResponseBodySerializer(result_list)
        return Response(data=res_serializer.data)


class ClientServiceListView(APIView):

    def get(self, request):
        """
        入力チェックを追加
        """
        req_serializer = ClientRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # query
        # client のリストのみを抽出
        # ただ、法人情報は頻繁に使われるので、これは含める
        user = self.request.user
        client = Client
        wheres = {
            'provider_account': user.account_id,
            'status': Client.Status.ENABLE.value,
        }

        if request.query_params.get('clientName'):
            wheres['name__contains'] = request.GET.get('clientName')
        if request.query_params.get('corporateName'):
            wheres['corporate__name__contains'] = request.GET.get('corporateName')

        clients = client.objects.select_related('corporate').filter(**wheres).all()

        # response
        res_serializer = ClientDataResponseBodySerializer(clients)
        return Response(data=res_serializer.data)


class ClientListDeleteView(APIView):

    def post(self, request):

        req_serializer = ClientDeleteRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = request.data
        result_list = []
        user_id = self.request.user.id
        datetime_now = make_aware(datetime.datetime.now())

        for delete_id in list(OrderedDict.fromkeys(params.get('ids'))):
            delete_client = Client.objects.get(pk=delete_id)
            delete_client.status = Client.Status.DISABLE.value
            delete_client.updated_by_id = user_id
            delete_client.updated_at = datetime_now
            delete_client.save()
            result_list.append(delete_id)

        return Response(data=result_list)


class ClientEditView(APIView):

    def get(self, request):
        req_serializer = ClientEditGetRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = req_serializer.data

        client_id = params.get('id')
        account_id = self.request.user.account_id

        if client_id:
            wheres = {
                'pk': client_id,
                'provider_account_id': account_id,
                'status': Client.Status.ENABLE.value,
            }
            try:
                client = Client.objects.get(**wheres)
            except Exception as e:
                print(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            client = Client()

        res_serializer = ClientEditResponseBodySerializer(client)
        return Response(data=res_serializer.data)

    def post(self, request):
        req_serializer = ClientEditPostRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        client_id = req_serializer.data.get('id')
        user = self.request.user
        datetime_now = make_aware(datetime.datetime.now())

        if client_id:
            try:
                client = Client.objects.get(pk=client_id, provider_account=user.account_id,
                                            status=Client.Status.ENABLE.value)
                corporate = Corporate.objects.get(pk=client.corporate_id, status=Corporate.Status.ENABLE.value)
            except Exception as e:
                print(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            client = Client()
            corporate = Corporate()

        try:
            corporate.name = req_serializer.data.get('corporateName')
            corporate.address = req_serializer.data.get('corporateAddress')
            corporate.executive_name = req_serializer.data.get('corporateExecutiveName')
            corporate.sales_name = req_serializer.data.get('corporateSalesName')
            corporate.status = Corporate.Status.ENABLE.value
            if not client_id:
                corporate.created_by_id = user.id
                corporate.created_at = datetime_now
            corporate.updated_by_id = user.id
            corporate.updated_at = datetime_now
            corporate.save()

            client.name = req_serializer.data.get('corporateName')  # 顧客名（暫定）
            client.provider_account_id = user.account_id
            client.corporate = corporate
            client.status = Client.Status.ENABLE.value
            if not client_id:
                client.created_by_id = user.id
                client.created_at = datetime_now
            client.updated_by_id = user.id
            client.updated_at = datetime_now
            client.save()
        except Exception as e:
            print(e)
            return Response(["DBエラーが発生しました"], status=status.HTTP_400_BAD_REQUEST)

        res_serializer = ClientEditResponseBodySerializer(client)
        return Response(data=res_serializer.data)


class ClientDetailView(APIView):

    def get(self, request):
        req_serializer = ClientDetailRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = req_serializer.data

        client_id = params.get('id')
        account_id = self.request.user.account_id

        if client_id:
            wheres = {
                'pk': client_id,
                'provider_account_id': account_id,
                'status': Client.Status.ENABLE.value,
            }
            try:
                client = Client.objects.get(**wheres)
            except Exception as e:
                print(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            client = Client()

        res_serializer = ClientDetailResponseBodySerializer(client)
        return Response(data=res_serializer.data)


class ClientCsvUploadView(APIView):
    """
    連絡先ユーザ一括追加CSVアップロード
    """
    parser_classes = [FormParser, MultiPartParser]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def post(self, request: Union[Request, HttpRequest]):
        csv_contents = request.data['csv'].read().decode('utf-8')
        importer = ClientCsvImporter(contents=csv_contents, operated_by=self.request.user)
        try:
            if not importer.is_valid():
                return Response({
                    'success': False,
                    'msg': 'パラメータが不正です',
                    'errors': importer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

            importer.import_clients()
        except ClientCsvImporter.UserDuplicateError:
            return Response({
                'success': False,
                'msg': 'しばらく時間をおいてもう一度やり直してください',
            }, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            print(e)
            return Response("エラーが発生しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'success': True})
