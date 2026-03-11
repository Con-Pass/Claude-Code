from logging import getLogger

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from conpass.models import Contract, Directory, DirectoryPermission, Group, MetaKey, MetaKeyDirectory, User
from conpass.models.constants import ContractTypeable
from conpass.services.directory.directory_service import DirectoryService
from conpass.views.directory.serializer.directory_serializer import DirectoryResponseBodySerializer, \
    DirectoryMenuResponseBodySerializer, DirectoryDeleteRequestBodySerializer
from conpass.views.directory.serializer.directory_detail_serializer import DirectoryDetailResponseBodySerializer, \
    DirectoryDetailRequestBodySerializer, DirectoryChildDetailResponseBodySerializer, DirectorySortRequestSerializer
from conpass.views.directory.serializer.directory_edit_serializer import SettingDirectoryRequestBodySerializer
from collections import OrderedDict

from django.utils.timezone import make_aware
from django.db.models import Prefetch, Q, Case, When, Value, BooleanField
from django.db.utils import DatabaseError

import datetime
import traceback

logger = getLogger(__name__)


class DirectoryListView(APIView):
    """
    階層一覧取得（一番上位の階層のみ）
    """

    def get(self, request):
        # ログインユーザーのアカウントID
        account_id = self.request.user.account_id
        directory_service = DirectoryService()
        prefetch=directory_service.get_permission_prefetch(self.request.user)

        directories = list(
            Directory.objects.filter(
                level=0,
                account_id=account_id,
                status=Directory.Status.ENABLE.value
            ).all()
            .annotate(
                sort_id_is_null=Case(
                    When(sort_id__isnull=True, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField()
                )
            ).order_by('sort_id_is_null', 'sort_id', 'name').prefetch_related(prefetch)
        )
        if self.request.user.permission_category:
            if self.request.user.permission_category.id !=1:
                directories = directory_service.filter_visible_directories(directories)
        else:
            directories = directory_service.filter_visible_directories(directories)
        res_serializer = DirectoryResponseBodySerializer(directories)
        return Response(data=res_serializer.data)


class DirectoryMenuListView(APIView):
    """
    階層メニュー用一覧取得
    """

    def get(self, request):
        # ログインユーザーのアカウントID
        account_id = self.request.user.account_id

        directory_service = DirectoryService()
        prefetch = directory_service.get_permission_prefetch(self.request.user)  # 表示設定情報を付与する

        directories = list(
            Directory.objects.filter(
                level=0,
                account_id=account_id,
                status=Directory.Status.ENABLE.value
            ).all()
            .annotate(
                sort_id_is_null=Case(
                    When(sort_id__isnull=True, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField()
                )
            ).order_by('sort_id_is_null', 'sort_id', 'name')
            .prefetch_related(prefetch))
        visible_directories = directory_service.filter_visible_directories(directories, self.request.user.is_bpo)
        for d in visible_directories:
            child_list = Directory.objects.filter(
                level=1,
                parent_id=d.id,
                account_id=account_id,
                status=Directory.Status.ENABLE.value
            ).all().annotate(
                sort_id_is_null=Case(
                    When(sort_id__isnull=True, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField()
                )
            ).order_by('sort_id_is_null', 'sort_id', 'name').prefetch_related(prefetch)
            visible_childs = directory_service.filter_visible_directories(list(child_list), self.request.user.is_bpo)
            d.child = visible_childs

        res_serializer = DirectoryMenuResponseBodySerializer(visible_directories)
        return Response(data=res_serializer.data)


class DirectoryDeleteView(APIView):

    def post(self, request):

        req_serializer = DirectoryDeleteRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = request.data
        result_list = []
        user_id = self.request.user.id
        datetime_now = make_aware(datetime.datetime.now())
        # ログインユーザーのアカウントID
        account_id = self.request.user.account_id

        for delete_id in list(OrderedDict.fromkeys(params.get('ids'))):
            if Contract.objects.exclude(status=Contract.Status.DISABLE.value).filter(directory_id=delete_id,
                                                                                     is_garbage=False).count() > 0:
                return Response({"msg": ["親フォルダに契約書が存在します。"]}, status=status.HTTP_400_BAD_REQUEST)
            # 子階層一覧取得
            delete_directory_child = Directory.objects.filter(parent_id=delete_id, account_id=account_id,
                                                              status=Directory.Status.ENABLE.value).all()
            # 契約書の有無をチェック
            for child in delete_directory_child:
                if Contract.objects.exclude(status=Contract.Status.DISABLE.value).filter(directory_id=child.id,
                                                                                         is_garbage=False).count() > 0:
                    return Response({"msg": ["子フォルダに契約書が存在します。"]}, status=status.HTTP_400_BAD_REQUEST)
            wheres = {
                'id': delete_id,
                'account': account_id
            }
            try:
                delete_directory = Directory.objects.get(**wheres)
            except Directory.DoesNotExist as e:
                logger.info(e)
                continue
            delete_directory.status = Directory.Status.DISABLE.value
            delete_directory.updated_by_id = user_id
            delete_directory.updated_at = datetime_now
            delete_directory.save()
            # 子階層削除
            for child in delete_directory_child:
                child.status = Directory.Status.DISABLE.value
                child.updated_by_id = user_id
                child.updated_at = datetime_now
                child.save()
                result_list.append(child.id)

            result_list.append(delete_id)

        return Response(data=result_list)


class DirectoryDetailView(APIView):
    """
    階層情報取得
    """

    def get(self, request):
        req_serializer = DirectoryDetailRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wheres = {
            'id': req_serializer.data.get('id'),
            'account': request.user.account
        }
        try:
            directory = Directory.objects.get(**wheres)
        except Directory.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        groups = []
        users = []
        if DirectoryPermission.objects.filter(directory_id=req_serializer.data.get('id'),
                                              status=Directory.Status.ENABLE.value).exists():
            directory_permissions = DirectoryPermission.objects.filter(
                directory_id=req_serializer.data.get('id'),
                status=Directory.Status.ENABLE.value).all()
            for permission in directory_permissions:
                if permission.group_id:
                    data = {
                        'id': permission.group.id,
                        'name': permission.group.name,
                    }
                    groups.append(data)
                if permission.user_id:
                    data = {
                        'id': permission.user.id,
                        'name': permission.user.username,
                    }
                    users.append(data)

        res_data = {
            'id': directory.id,
            'name': directory.name,
            'type': directory.type,
            'memo': directory.memo,
            'status': directory.status,
            'sort_id': directory.sort_id,
            'groups': groups,
            'users': users,
        }

        res_serializer = DirectoryDetailResponseBodySerializer(res_data)
        return Response(data=res_serializer.data)


class DirectoryUpdateView(APIView):
    """
    階層情報取得更新
    権限設定、メタ情報更新
    """

    def post(self, request):
        req_serializer = SettingDirectoryRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        request_data = req_serializer.data
        login_user = request.user
        now = make_aware(datetime.datetime.now())

        try:
            # 親階層作成
            directory = self.create_directory(request_data, login_user, now)
            if isinstance(directory, Response):
                # create_directoryからResponseが返された場合は、それをそのまま返す
                return directory

            # 親階層の権限設定
            self.create_directory_permission(request_data, login_user, directory, now)

            # 親階層のメタ情報設定
            self.create_directory_meta(request_data, login_user, directory, now)

            # 子階層作成
            child = self.create_directory_child(request_data, login_user, directory, now)
            if isinstance(child, Response):
                return child

        except Directory.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        except MetaKeyDirectory.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"msg": ["登録しました"]}, status.HTTP_200_OK)

    def validate_sort_id(self, sort_id):
        if sort_id is not None:
            if 1 <= sort_id <= 9999:
                return sort_id
            else:
                return Response(
                    {"msg": ["表示順位は1から9999の間でなければなりません。"]},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return None

    # 親階層作成
    def create_directory(self, request_data: OrderedDict, login_user: User, now: datetime.datetime):
        wheres = {
            'id': request_data.get('id'),
            'account': login_user.account
        }
        directory = Directory.objects.get(**wheres) \
            if request_data.get('id') else Directory()
        directory.name = request_data['name']
        directory.level = 0
        directory.type = request_data['type']
        directory.status = Directory.Status.ENABLE.value
        directory.account = login_user.account
        directory.memo = request_data['memo']
        if not request_data['id']:
            directory.created_by = login_user
            directory.created_at = now
        directory.updated_by = login_user
        directory.updated_at = now
        sort_id_response = self.validate_sort_id(request_data.get('sort_id'))
        if isinstance(sort_id_response, Response):
            return sort_id_response
        else:
            directory.sort_id = sort_id_response
        directory.save()
        return directory

    # 権限設定
    def create_directory_permission(self, request_data: OrderedDict, login_user: User, directory: Directory,
                                    now: datetime.datetime):
        users = request_data['users']
        groups = request_data['groups']
        if DirectoryPermission.objects.filter(directory_id=directory.id,
                                              status=Directory.Status.ENABLE.value).exists():
            DirectoryPermission.objects.filter(
                directory_id=directory.id,
                status=Directory.Status.ENABLE.value).delete()

        for user in users:
            directory_permission = DirectoryPermission()
            directory_permission.is_visible = True
            directory_permission.status = DirectoryPermission.Status.ENABLE.value
            directory_permission.directory_id = directory.id
            directory_permission.user_id = user.get('id')
            directory_permission.created_by = login_user
            directory_permission.created_at = now
            directory_permission.updated_by = login_user
            directory_permission.updated_at = now
            directory_permission.save()

        for group in groups:
            directory_permission = DirectoryPermission()
            directory_permission.is_visible = True
            directory_permission.status = DirectoryPermission.Status.ENABLE.value
            directory_permission.directory_id = directory.id
            directory_permission.group_id = group.get('id')
            directory_permission.created_by = login_user
            directory_permission.created_at = now
            directory_permission.updated_by = login_user
            directory_permission.updated_at = now
            directory_permission.save()

    # 親階層のメタ情報設定
    def create_directory_meta(self, request_data: OrderedDict, login_user: User, directory: Directory,
                              now: datetime.datetime):
        # メタ情報設定（デフォルト項目）
        default_list = request_data['defaultKeyList']
        for data in default_list:
            meta_key_directory = MetaKeyDirectory.objects.get(Q(pk=data.get('meta_key_directory_id')),
                                                              Q(key__type=MetaKey.Type.DEFAULT.value) | Q(
                                                                  account_id=login_user.account_id)) \
                if data.get('meta_key_directory_id') else MetaKeyDirectory()
            meta_key_directory.key_id = data.get('id')
            meta_key_directory.directory_id = directory.id
            meta_key_directory.is_visible = data.get('is_visible')
            meta_key_directory.account = login_user.account
            if not data.get('meta_key_directory_id'):
                meta_key_directory.created_by = login_user
                meta_key_directory.created_at = now
            meta_key_directory.updated_by = login_user
            meta_key_directory.updated_at = now
            meta_key_directory.save()

        # メタ情報設定（自由項目項目）
        free_list = request_data['freeKeyList']
        for data in free_list:
            meta_key_directory = MetaKeyDirectory.objects.get(Q(pk=data.get('meta_key_directory_id')),
                                                              Q(key__type=MetaKey.Type.FREE.value) | Q(
                                                                  account_id=login_user.account_id)) \
                if data.get('meta_key_directory_id') else MetaKeyDirectory()
            meta_key_directory.key_id = data.get('id')
            meta_key_directory.directory_id = directory.id
            meta_key_directory.is_visible = data.get('is_visible')
            meta_key_directory.account = login_user.account
            if not data.get('meta_key_directory_id'):
                meta_key_directory.created_by = login_user
                meta_key_directory.created_at = now
            meta_key_directory.updated_by_by = login_user
            meta_key_directory.updated_at = now
            meta_key_directory.save()

    # 子階層作成
    def create_directory_child(self, request_data: OrderedDict, login_user: User, directory: Directory,
                               now: datetime.datetime):
        child_list = request_data['childList']
        for data in child_list:
            if not data.get('name'):
                continue
            directory_child = Directory.objects.get(pk=data.get('id')) \
                if data.get('id') else Directory()
            directory_child.name = data.get('name')
            directory_child.level = 1
            directory_child.type = request_data['type']
            directory_child.status = data.get('status')
            directory_child.account = login_user.account
            directory_child.parent_id = directory.id
            if not data.get('id'):
                directory_child.created_by = login_user
                directory_child.created_at = now
            directory_child.updated_by = login_user
            directory_child.updated_at = now
            sort_id_response = self.validate_sort_id(data.get('sort_id'))
            if isinstance(sort_id_response, Response):
                return sort_id_response
            else:
                directory_child.sort_id = sort_id_response
            directory_child.save()

            request_data['users'] = data.get('users')
            request_data['groups'] = data.get('groups')
            # 子ディレクトリ権限設定
            self.create_directory_permission(request_data, login_user, directory_child, now)


class DirectoryChildListView(APIView):
    """
    子階層情報取得
    """

    def get(self, request):
        req_serializer = DirectoryDetailRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # ログインユーザーのアカウントID
        account_id = self.request.user.account_id
        directory_list = Directory.objects.filter(
            parent_id=req_serializer.data.get('id'),
            account_id=account_id,
            status=Directory.Status.ENABLE.value).all().annotate(
                sort_id_is_null=Case(
                    When(sort_id__isnull=True, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField()
                )
        ).order_by('sort_id_is_null', 'sort_id', 'name')

        result_list = []
        for directory in directory_list:
            groups = []
            users = []
            if DirectoryPermission.objects.filter(directory_id=req_serializer.data.get('id'),
                                                  status=Directory.Status.ENABLE.value).exists():
                directory_permissions = DirectoryPermission.objects.filter(
                    directory_id=directory.id,
                    status=Directory.Status.ENABLE.value).all()
                for permission in directory_permissions:
                    if permission.group_id:
                        data = {
                            'id': permission.group.id,
                            'name': permission.group.name,
                        }
                        groups.append(data)
                    if permission.user_id:
                        data = {
                            'id': permission.user.id,
                            'name': permission.user.username,
                        }
                        users.append(data)

            res_data = {
                'id': directory.id,
                'name': directory.name,
                'type': directory.type,
                'memo': directory.memo,
                'status': directory.status,
                'sort_id': directory.sort_id,
                'groups': groups,
                'users': users,
            }
            result_list.append(res_data)

        res_serializer = DirectoryChildDetailResponseBodySerializer(result_list)
        return Response(data=res_serializer.data)


class DirectoryCheckDeleteView(APIView):

    def post(self, request):

        req_serializer = DirectoryDetailRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if Contract.objects.exclude(status=Contract.Status.DISABLE.value)\
                           .filter(directory_id=request.data.get('id'), is_garbage=False).count() > 0:
            return Response({"msg": ["契約書が存在します。"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"msg": []}, status=status.HTTP_200_OK)


class DirectoryAllowedListView(APIView):

    def get(self, request):
        directory_service = DirectoryService()
        directories = directory_service.get_allowed_directories(self.request.user,
                                                                ContractTypeable.ContractType.CONTRACT.value)
        res_serializer = DirectoryResponseBodySerializer(directories)
        return Response(data=res_serializer.data)


class DirectorySortEditView(APIView):

    def post(self, request):
        # 修正されたシリアライザを使用してリクエストデータを検証
        req_serializer = DirectorySortRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # 検証されたデータを取得
        validated_data = req_serializer.validated_data["params"]

        # validated_dataを使ってビジネスロジックを実装
        # 例: データベースのレコードを更新
        for item in validated_data:
            id = item.get("id")
            sort_id = item.get("sort_id")
            varidate_id = DirectoryUpdateView()
            sort_id_response = varidate_id.validate_sort_id(sort_id)
            if isinstance(sort_id_response, Response):
                return sort_id_response
            else:
                Directory.objects.filter(id=id).update(sort_id=sort_id_response)
        # 応答を返す
        return Response({"msg": "更新が完了しました。"}, status=status.HTTP_200_OK)
