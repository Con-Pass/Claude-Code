from logging import getLogger

from django.db.models import Prefetch
from rest_framework import status
from rest_framework.response import Response

from conpass.views.sys.common import SysAPIView
from conpass.views.sys.corporate.serializer.corporate_serializer import SysCorporateRequestBodySerializer, \
    SysCorporateResponseBodySerializer
from conpass.views.sys.corporate.serializer.corporate_detail_serializer import SysCorporateDetailRequestBodySerializer, \
    SysCorporateDetailResponseBodySerializer
from conpass.models import Corporate, Client, User

logger = getLogger(__name__)


class SysCorporateListView(SysAPIView):

    def get(self, request):
        # request
        req_serializer = SysCorporateRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wheres = {}

        # 絞り込み
        if req_serializer.data.get('corporateName'):
            wheres['name__contains'] = req_serializer.data.get('corporateName')

        # query
        corporate_list = list(Corporate.objects.filter(**wheres).all())

        # response
        res_serializer = SysCorporateResponseBodySerializer(corporate_list)
        return Response(data=res_serializer.data)


class SysCorporateDetailView(SysAPIView):

    def get(self, request):
        req_serializer = SysCorporateDetailRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        corporate_id = req_serializer.data.get('id')
        if corporate_id:
            try:
                corporate = Corporate.objects.get(pk=corporate_id)
            except User.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            corporate = Corporate()

        # ユーザー一覧
        user_list = User.objects.filter(status=User.Status.ENABLE.value,
                                        corporate_id=corporate_id, type=User.Type.ACCOUNT.value).all()

        # 連絡先ー一覧
        client_list = Client.objects.filter(corporate_id=corporate_id, status=Client.Status.ENABLE.value).all()

        # 連絡先のユーザ
        client_users = Client.objects.filter(status=Client.Status.ENABLE.value).exclude(corporate=None).all() \
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

        res_serializer = SysCorporateDetailResponseBodySerializer(data)
        return Response(data=res_serializer.data)
