import traceback
from logging import getLogger

from rest_framework import status, serializers
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from conpass.models.constants import Statusable
from conpass.services.paginate.paginate import StandardResultsSetPagination
from conpass.views.group.serializer.group_serializer import GroupRequestBodySerializer, GroupResponseBodySerializer, \
    GroupDeleteRequestBodySerializer, GroupUserResponseBodySerializer, GroupResponseSerializer
from conpass.views.group.serializer.group_detail_serializer import GroupDetailRequestBodySerializer, \
    GroupDetailResponseBodySerializer
from conpass.views.group.serializer.group_edit_serializer import GroupEditRequestBodySerializer
from conpass.models import Group, User, Permission, PermissionTarget, Account, PermissionCategory
import datetime
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError
from django.db.models import Prefetch

logger = getLogger(__name__)


class SortGroupListView(generics.ListAPIView):
    """
    連絡先一覧画面検索処理
    """
    serializer_class = GroupResponseSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        検索処理追加のためオーバーライド
        """
        # query
        request = self.request
        account_id = request.user.account_id

        wheres = {
            'account_id': account_id,
            'status': Group.Status.ENABLE.value,
        }

        # 絞り込み
        if request.query_params.get('groupName'):
            wheres['name__icontains'] = request.GET.get('groupName')

        group_list = list(Group.objects.filter(**wheres).all())

        queryset = group_list
        return queryset


class GroupListView(APIView):

    def get(self, request):
        # request
        req_serializer = GroupRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        account_id = self.request.user.account_id

        wheres = {
            'account_id': account_id,
            'status': Group.Status.ENABLE.value,
        }

        if req_serializer.data.get('groupName'):
            wheres['name__icontains'] = req_serializer.data.get('groupName')

        # query
        group_list = list(Group.objects.filter(**wheres).all())

        # response
        res_serializer = GroupResponseBodySerializer(group_list)
        return Response(data=res_serializer.data)


class GroupUserListView(APIView):

    def get(self, request):
        account_id = self.request.user.account_id

        wheres = {
            'account_id': account_id,
            'type': User.Type.ACCOUNT.value,
            'status': User.Status.ENABLE.value,
            'is_bpo': False
        }

        # query
        user_list = list(User.objects.filter(**wheres).all())

        # response
        res_serializer = GroupUserResponseBodySerializer(user_list)
        return Response(data=res_serializer.data)


class GroupDeleteView(APIView):

    def post(self, request):

        req_serializer = GroupDeleteRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = request.data
        user_id = self.request.user.id
        # ログインユーザーのアカウントID
        account_id = self.request.user.account_id
        result_list = []

        for delete_id in list(params['ids']):
            wheres = {
                'id': delete_id,
                'account': account_id
            }
            try:
                delete_group = Group.objects.get(**wheres)
            except Group.DoesNotExist as e:
                logger.info(e)
                continue
            delete_group.status = Group.Status.DISABLE.value
            delete_group.updated_by_id = user_id
            delete_group.updated_at = make_aware(datetime.datetime.now())
            delete_group.save()
            result_list.append(delete_id)

        return Response(data=result_list)


class GroupDetailView(APIView):

    def get(self, request):
        req_serializer = GroupDetailRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        group_id = req_serializer.data.get('id')
        # ログインユーザーのアカウントID
        account_id = self.request.user.account_id

        if group_id:
            try:
                wheres = {
                    'id': group_id,
                    'account': account_id
                }
                group = Group.objects.prefetch_related(Prefetch('user_group',
                                                                queryset=User.objects.exclude(
                                                                    status=User.Status.DISABLE.value))) \
                    .get(**wheres)
            except Group.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            group = Group()

        res_serializer = GroupDetailResponseBodySerializer(group)
        return Response(data=res_serializer.data)


class GroupEditView(APIView):

    def post(self, request):
        req_serializer = GroupEditRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        group_id = req_serializer.data.get('id')  # 編集対象（無い時は新規作成）
        user_id = self.request.user.id  # 操作している人
        account_id = self.request.user.account_id

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


class GroupPermissionView(APIView):

    def post(self, request):
        params = request.data
        for param_id in params:
            permission_id = param_id.get('permission_category_id')
            wheres_base = {
                'user_id': param_id.get('id'),
                'status': Statusable.Status.ENABLE.value,
                'target__status': Statusable.Status.ENABLE.value
            }
            permission_base = Permission.objects.select_related('target').filter(**wheres_base)
            now = make_aware(datetime.datetime.now())
            login_user = self.request.user
            permission_all = []
            user_id = param_id.get('id')
            # ログインユーザーのアカウントID
            account_id = self.request.user.account_id
            try:
                wheres = {
                    'id': user_id,
                    'account': account_id
                }
                user = User.objects.get(**wheres)
                if permission_id is not None:
                    # permission_id が指定されている場合、permission_category_id を上書きする
                    user.permission_category_id = permission_id
                    try:
                        permission_category = PermissionCategory.objects.filter(permission_category_id=permission_id)
                        for param_permission in permission_category:
                            target_id = param_permission.target.id
                            wheres = {
                                'target_id': target_id
                            }
                            try:
                                permission = permission_base.filter(**wheres).first()
                            except Permission.DoesNotExist as e:
                                logger.info(f"{e}: {traceback.format_exc()}")
                                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

                            permission.is_allow = param_permission.is_allow
                            if self.request.user.account.plan == Account.Plan.LIGHT.value:
                                if target_id in [PermissionTarget.Target.DISP_WORKFLOW_SETTING.value,
                                                 PermissionTarget.Target.DISP_CLIENT_SETTING.value]:
                                    permission.is_allow = False

                            permission.updated_by = login_user
                            permission.updated_at = now
                            permission_all.append(permission)
                        Permission.objects.bulk_update(permission_all, fields=['is_allow', 'updated_by', 'updated_at'])
                    except DatabaseError as e:
                        logger.error(f"{e}: {traceback.format_exc()}")
                        return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                else:
                    # permission_id が指定されていない場合、現在の permission_category_id を削除して上書きする
                    user.permission_category_id = None
                    try:
                        for param_permission in params.get('permissions'):
                            target_id = param_permission.get('target').get('id')
                            wheres = {
                                'target_id': target_id
                            }
                            try:
                                permission = permission_base.filter(**wheres).get()
                            except Permission.DoesNotExist as e:
                                logger.info(f"{e}: {traceback.format_exc()}")
                                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

                            permission.is_allow = param_permission.get('isAllow')
                            if self.request.user.account.plan == Account.Plan.LIGHT.value:
                                if target_id in [PermissionTarget.Target.DISP_WORKFLOW_SETTING.value,
                                                 PermissionTarget.Target.DISP_CLIENT_SETTING.value]:
                                    permission.is_allow = False

                            permission.updated_by = login_user
                            permission.updated_at = now
                            permission_all.append(permission)
                        Permission.objects.bulk_update(permission_all, fields=['is_allow', 'updated_by', 'updated_at'])
                    except DatabaseError as e:
                        logger.error(f"{e}: {traceback.format_exc()}")
                        return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                user.save()
            except User.DoesNotExist:
                logger.info(f"ユーザーが存在しません: id={user_id}")
        return Response({"msg": ["設定しました"]}, status=status.HTTP_200_OK)
