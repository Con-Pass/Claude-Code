import traceback
from logging import getLogger

from rest_framework import status, serializers
from rest_framework.response import Response

from conpass.views.sys.common import SysAPIView
from conpass.views.sys.group.serializer.group_serializer import GroupRequestBodySerializer, GroupResponseBodySerializer, \
    GroupDeleteRequestBodySerializer, GroupUserResponseBodySerializer
from conpass.views.sys.group.serializer.group_detail_serializer import GroupDetailRequestBodySerializer, \
    GroupDetailResponseBodySerializer, GroupAccountListSerializer
from conpass.views.sys.group.serializer.group_edit_serializer import GroupEditRequestBodySerializer, \
    GroupAccountResponseBodySerializer
from conpass.models import Group, User, Account, Client, Corporate
import datetime
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError

logger = getLogger(__name__)


class SysGroupListView(SysAPIView):

    def get(self, request):
        # request
        req_serializer = GroupRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wheres = {}

        if req_serializer.data.get('groupName'):
            wheres['name__contains'] = req_serializer.data.get('groupName')

        # query
        group_list = list(Group.objects.filter(**wheres).all())

        # response
        res_serializer = GroupResponseBodySerializer(group_list)
        return Response(data=res_serializer.data)


class SysGroupAccountListView(SysAPIView):

    def get(self, request):
        # query
        account_list = list(Account.objects.filter(status=Account.Status.ENABLE.value).all())

        # response
        res_serializer = GroupAccountResponseBodySerializer(account_list)
        return Response(data=res_serializer.data)


class SysGroupUserListView(SysAPIView):

    def get(self, request):
        wheres = {
            'type': User.Type.ACCOUNT.value,
            'status': User.Status.ENABLE.value,
        }

        # query
        user_list = list(User.objects.filter(**wheres).all())

        # response
        res_serializer = GroupUserResponseBodySerializer(user_list)
        return Response(data=res_serializer.data)


class SysGroupDeleteView(SysAPIView):

    def post(self, request):

        req_serializer = GroupDeleteRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = request.data
        user_id = self.request.user.id
        result_list = []

        for delete_id in list(params['ids']):
            delete_group = Group.objects.get(pk=delete_id)
            delete_group.status = Group.Status.DISABLE.value
            delete_group.updated_by_id = user_id
            delete_group.updated_at = make_aware(datetime.datetime.now())
            delete_group.save()
            result_list.append(delete_id)

        return Response(data=result_list)


class SysGroupDetailView(SysAPIView):

    def get(self, request):
        req_serializer = GroupDetailRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        group_id = req_serializer.data.get('id')

        if group_id:
            try:
                group = Group.objects.prefetch_related('user_group').get(pk=group_id)
            except Group.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            group = Group()

        res_serializer = GroupDetailResponseBodySerializer(group)
        return Response(data=res_serializer.data)


class SysGroupEditView(SysAPIView):

    def post(self, request):
        req_serializer = GroupEditRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        group_id = req_serializer.data.get('id')  # 編集対象（無い時は新規作成）
        user_id = self.request.user.id  # 操作している人
        account_id = req_serializer.data.get('accountId')  # アカウントID

        datetime_now = make_aware(datetime.datetime.now())
        # 重複チェック

        if group_id:
            try:
                group = Group.objects.get(pk=group_id, account_id=account_id)
            except Group.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            group = Group()

        try:
            group.name = req_serializer.data.get('name')
            group.description = req_serializer.data.get('description')
            group.account_id = account_id
            group.status = req_serializer.data.get('status')
            if not group_id:
                group.created_by_id = user_id
                group.created_at = datetime_now
            group.updated_by_id = user_id
            group.updated_at = datetime_now
            group.save()
            if req_serializer.data.get('selectUsers'):
                group.user_group.clear()
                for id in req_serializer.data.get('selectUsers'):
                    user = User.objects.get(pk=id, status=User.Status.ENABLE.value)
                    user.group.add(group)
                    user.save()

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=200)
