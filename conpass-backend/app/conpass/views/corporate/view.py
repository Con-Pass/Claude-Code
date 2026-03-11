from logging import getLogger
from rest_framework import generics
from django.db.models import Prefetch
from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from conpass.services.paginate.paginate import StandardResultsSetPagination
from conpass.views.corporate.serializer.corporate_serializer import CorporateRequestBodySerializer, \
    CorporateResponseBodySerializer, CorporateResponseSerializer, CorporateDeleteRequestBodySerializer
from conpass.views.corporate.serializer.corporate_detail_serializer import CorporateDetailRequestBodySerializer, \
    CorporateDetailResponseBodySerializer
from conpass.views.corporate.serializer.corporate_edit_serializer import CorporateEditRequestBodySerializer, \
    CorporateEditResponseBodySerializer
from conpass.models import Account, Corporate, User, Client
from collections import OrderedDict
import datetime
from django.utils.timezone import make_aware

logger = getLogger(__name__)


class SortCorporateListView(generics.ListAPIView):
    """
    連絡先一覧画面検索処理
    """
    serializer_class = CorporateResponseSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        検索処理追加のためオーバーライド
        """
        # request
        req_serializer = CorporateRequestBodySerializer(data=self.request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # ログインユーザのaccount_id
        account_id = self.request.user.account_id

        wheres = {
            'account_id': account_id,
            'status': Corporate.Status.ENABLE.value,
        }
        # 絞り込み
        if req_serializer.data.get('corporateName'):
            wheres['name__contains'] = req_serializer.data.get('corporateName')

        # query
        corporate_list = list(Corporate.objects.filter(**wheres).all())

        return corporate_list


class CorporateListDeleteView(APIView):

    def post(self, request):

        req_serializer = CorporateDeleteRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = request.data
        result_list = []
        user_id = self.request.user.id
        account_id = self.request.user.account_id
        datetime_now = make_aware(datetime.datetime.now())

        for delete_id in list(OrderedDict.fromkeys(params.get('ids'))):
            wheres = {
                'id': delete_id,
                'account_id': account_id,
                'status': Corporate.Status.ENABLE.value,
            }
            delete_corporate = Corporate.objects.get(**wheres)
            delete_corporate.status = Corporate.Status.DISABLE.value
            delete_corporate.updated_by_id = user_id
            delete_corporate.updated_at = datetime_now
            delete_corporate.save()
            result_list.append(delete_id)

        return Response(data=result_list)


class CorporateDetailView(APIView):

    def get(self, request):
        req_serializer = CorporateDetailRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        corporate_id = req_serializer.data.get('id')
        # ログインユーザーのアカウントID
        account_id = self.request.user.account_id
        wheres = {
            'id': corporate_id,
            'account_id': account_id,
            'status': Corporate.Status.ENABLE.value,
        }
        if corporate_id:
            try:
                corporate = Corporate.objects.get(**wheres)
            except Corporate.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        # ユーザー一覧
        user_list = User.objects.filter(status=User.Status.ENABLE.value, account_id=account_id,
                                        is_bpo=False, corporate_id=corporate_id, type=User.Type.ACCOUNT.value).all()

        # 連絡先ー一覧
        client_list = Client.objects.filter(provider_account=account_id, corporate_id=corporate_id,
                                            status=Client.Status.ENABLE.value).all()

        # 連絡先のユーザ
        client_users = Client.objects.filter(provider_account=account_id, status=Client.Status.ENABLE.value) \
            .exclude(corporate=None).all() \
            .prefetch_related(Prefetch('user_client',
                                       queryset=User.objects.filter(type=User.Type.CLIENT.value,
                                                                    status=User.Status.ENABLE.value).all()))

        client_user_list = []
        for c in client_users:
            # 連絡先に紐づく利用者ごとに行を作成
            users = c.user_client.all()
            if len(users):
                for u in users:
                    if u.corporate_id == corporate_id:
                        client_user_list.append(u)

        data = {
            'corporate': corporate,
            'user_list': user_list,
            'client_list': client_list,
            'client_user_list': client_user_list,
        }

        res_serializer = CorporateDetailResponseBodySerializer(data)
        return Response(data=res_serializer.data)


class CorporateEditView(APIView):

    def get(self, request):
        req_serializer = CorporateDetailRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        corporate_id = req_serializer.data.get('id')
        wheres = {
            'id': corporate_id,
            'account_id': self.request.user.account_id,
            'status': Corporate.Status.ENABLE.value,
        }
        if corporate_id:
            try:
                corporate = Corporate.objects.get(**wheres)
            except User.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            corporate = Corporate()

        res_serializer = CorporateEditResponseBodySerializer(corporate)
        return Response(data=res_serializer.data)

    def post(self, request):
        req_serializer = CorporateEditRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        corporate_id = req_serializer.data.get('id')
        datetime_now = make_aware(datetime.datetime.now())
        wheres = {
            'id': corporate_id,
            'account_id': self.request.user.account_id,
            'status': Corporate.Status.ENABLE.value,
        }
        if corporate_id:
            try:
                corporate = Corporate.objects.get(**wheres)
            except Exception as e:
                print(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            corporate = Corporate()

        try:
            corporate.name = req_serializer.data.get('name')
            corporate.address = req_serializer.data.get('address')
            corporate.executive_name = req_serializer.data.get('executiveName')
            corporate.sales_name = req_serializer.data.get('salesName')
            corporate.service = req_serializer.data.get('service')
            corporate.url = req_serializer.data.get('url')
            corporate.tel = req_serializer.data.get('tel')
            corporate.status = req_serializer.data.get('status')
            corporate.account_id = self.request.user.account_id
            if not corporate_id:
                corporate.created_by_id = self.request.user.id
                corporate.created_at = datetime_now
            corporate.updated_by_id = self.request.user.id
            corporate.updated_at = datetime_now
            corporate.save()
        except Exception as e:
            print(e)
            return Response(["DBエラーが発生しました"], status=status.HTTP_400_BAD_REQUEST)

        return Response(status=200)
