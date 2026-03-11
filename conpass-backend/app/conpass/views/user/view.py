import traceback
import uuid
import pyotp
from logging import getLogger
from typing import Union

from django.db.models import Prefetch
from django.http import HttpRequest
from django.db import transaction
from rest_framework import generics
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.mailer.user_mailer import UserMailer
from conpass.models.constants import Statusable, OtpInterval
from conpass.services.paginate.paginate import StandardResultsSetPagination
from conpass.services.user.user_csv_importer import UserClientCsvImporter, UserCsvImporter
from conpass.services.user.user_service import UserService
from conpass.views.user.serializer.user_serializer import UserRequestBodySerializer, \
    UserResponseBodySerializer, UserDeleteRequestBodySerializer, UserResponseSerializer, UserDataRequestBodySerializer, \
    UserDataResponseBodySerializer, UserPermissionsResponseBodySerializer, UserPermissionsListResponseBodySerializer, \
    UserPermissionsRequestSerializer, UserPermissionCategoryResponseBodySerializer, \
    UserPermissionCategoryRequestSerializer
from conpass.views.user.serializer.user_detail_serializer import UserDetailRequestBodySerializer, \
    UserDetailResponseBodySerializer
from conpass.views.user.serializer.user_edit_serializer import UserEditRequestBodySerializer, \
    UserEditResponseBodySerializer
from conpass.models import User, Client, Permission, PermissionTarget, Account, PermissionCategory, \
    PermissionCategoryKey
import datetime
from django.utils.timezone import make_aware
from django.contrib.auth.hashers import make_password
from django.db.utils import DatabaseError
from django.db.models import Q

logger = getLogger(__name__)


class SortUserListView(generics.ListAPIView):
    """
    利用者一覧画面検索処理
    """
    serializer_class = UserResponseSerializer
    pagination_class = StandardResultsSetPagination

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        """
        検索処理追加のためオーバーライド
        """
        req_serializer = UserRequestBodySerializer(data=self.request.query_params)
        req_serializer.is_valid(raise_exception=True)

        account_id = self.request.user.account_id

        wheres = {
            'account_id': account_id,
            'type': req_serializer.data.get('type'),
            'status': User.Status.ENABLE.value,
            'is_bpo': False
        }
        if req_serializer.data.get('userName'):
            wheres['username__icontains'] = req_serializer.data.get('userName')
        if req_serializer.data.get('type') == User.Type.CLIENT.value:
            if req_serializer.data.get('clientId'):
                wheres['client_id'] = req_serializer.data.get('clientId')

        queryset = User.objects.filter(**wheres)
        return queryset


class UserListView(APIView):

    def get(self, request):
        # request
        req_serializer = UserRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        account_id = self.request.user.account_id

        wheres = {
            'account_id': account_id,
            'type': User.Type.ACCOUNT.value,
            'is_bpo': False
        }
        if req_serializer.data.get('userName'):
            wheres['username__contains'] = req_serializer.data.get('userName')

        # query
        user_list = list(User.objects.filter(**wheres).all())

        # response
        res_serializer = UserResponseBodySerializer(user_list)
        return Response(data=res_serializer.data)


class UserDeleteView(APIView):

    def post(self, request):
        # TODO: アカウント内のユーザを削除する権限はすべてのユーザがもっているのか

        req_serializer = UserDeleteRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = request.data
        user = self.request.user
        result_list = []

        user_service = UserService()
        now = make_aware(datetime.datetime.now())
        for delete_id in list(params['ids']):
            if delete_id == user.id:
                return Response({"msg": ["削除エラー"]}, status=status.HTTP_400_BAD_REQUEST)
            try:
                delete_user = User.objects.get(
                    pk=delete_id,
                    account_id=self.request.user.account_id,
                )
            except User.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
            user_service.delete_user_data(delete_user, user, now)
            result_list.append(delete_id)

        return Response(data=result_list)


class UserDetailView(APIView):

    def get(self, request):
        user_id = request.query_params.get('id')
        my_account_id = self.request.user.account_id

        wheres = {
            'pk': user_id,
            'account_id': my_account_id,
            'status': User.Status.ENABLE.value,
            'is_bpo': False
        }
        if user_id:
            try:
                user = User.objects.get(**wheres)
                if user.otp_secret:
                    user.otpSecretUri = pyotp.totp.TOTP(user.otp_secret, interval=OtpInterval.OtpIntervalTime.TIME30.value) \
                        .provisioning_uri(name=user.login_name, issuer_name="ConPass")
                else:
                    user.otpSecretUri = None
            except User.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            user = User()

        res_serializer = UserDetailResponseBodySerializer(user)
        return Response(data=res_serializer.data)


class UserEditView(APIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.user_mailer = UserMailer()

    def post(self, request):
        req_serializer = UserEditRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        edit_user_id = req_serializer.data.get('id')  # 編集対象（無い時は新規作成）
        user_id = self.request.user.id  # 操作している人
        account_id = self.request.user.account_id

        login_name = req_serializer.data.get('loginName')
        client_id = req_serializer.data.get('clientId')
        user_type = req_serializer.data.get('type')
        user_name = req_serializer.data.get('username')

        check_account = {
            'account_id': account_id,
            'status': User.Status.ENABLE.value,
            'type': User.Type.ACCOUNT.value,
            'is_bpo': False,
        }
        persons = User.objects.filter(**check_account).exclude(pk=edit_user_id).all()
        cleaned_names = [person.username.replace(' ', '').replace('　', '').replace('\t', '') for person in persons]
        cleaned_username = user_name.replace(' ', '').replace('　', '').replace('\t', '')

        datetime_now = make_aware(datetime.datetime.now())
        # 重複チェック
        check_login_name = f"{login_name}:{client_id}" if user_type == User.Type.CLIENT.value and client_id else login_name
        if User.objects.exclude(pk=edit_user_id).filter(login_name=check_login_name).count() > 0:
            if user_type == User.Type.ACCOUNT.value:
                return Response({"msg": ["ログインIDが重複しています。"]}, status=status.HTTP_400_BAD_REQUEST)
            elif user_type == User.Type.CLIENT.value:
                return Response({"msg": ["連絡先のメールアドレスが重複しています。"]}, status=status.HTTP_400_BAD_REQUEST)

        wheres = {'login_name': login_name, 'account_id': account_id}
        if User.objects.exclude(pk=edit_user_id).filter(**wheres).count() > 0:
            return Response({"msg": ["ユーザーのメールアドレスで使用済みです"]}, status=status.HTTP_400_BAD_REQUEST)

        if user_type == User.Type.ACCOUNT.value:
            if cleaned_username in cleaned_names:
                return Response({"msg": ["名前が重複しています。"]}, status=status.HTTP_400_BAD_REQUEST)

        if edit_user_id:
            try:
                user = User.objects.get(pk=edit_user_id, account_id=account_id, status=User.Status.ENABLE.value)
            except User.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            user = User()

        try:
            with transaction.atomic():
                user.login_name = login_name

                # 更新時はパスワードが入力された場合のみ更新
                if req_serializer.data.get('inputPassword'):
                    user.password = make_password(req_serializer.data.get('inputPassword'))

                user.username = req_serializer.data.get('username')
                user.division = req_serializer.data.get('division')
                user.position = req_serializer.data.get('position')
                user.email = login_name
                user.tel = req_serializer.data.get('tel')
                user.memo = req_serializer.data.get('memo')
                user.status = req_serializer.data.get('status')
                user.mfa_status = req_serializer.data.get('mfaStatus')
                user.account_id = account_id
                user.type = user_type
                user.is_bpo = False  # 利用者側は false のみ
                if user.type == User.Type.CLIENT.value and client_id:
                    try:
                        client = Client.objects.get(
                            id=client_id,
                            provider_account_id=self.request.user.account_id,
                            status=Client.Status.ENABLE.value,
                        )
                        user.client_id = client.id
                        user.login_name = f"{user.login_name}:{user.client_id}"
                    except Client.DoesNotExist as e:
                        logger.info(e)
                        return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
                if not edit_user_id:
                    user.created_by_id = user_id
                    user.created_at = datetime_now
                    user.otp_secret = pyotp.random_base32()
                user.updated_by_id = user_id
                user.updated_at = datetime_now
                user.save()

                # 通常ユーザの新規作成時は権限設定もあわせて行う
                if not edit_user_id and user.type == User.Type.ACCOUNT.value:
                    permission_category_id = req_serializer.data.get('permission_category_id')
                    user_service = UserService()
                    all_targets = [target.value for target in PermissionTarget.Target]

                    # 不許可の権限を格納するリスト
                    deny_targets = []

                    is_allow_filter = Q(
                        permission_category_id=permission_category_id,
                        status=PermissionCategory.Status.ENABLE.value,
                        is_allow=False,
                        account_id=account_id
                    ) | Q(
                        permission_category_id=permission_category_id,
                        status=PermissionCategory.Status.ENABLE.value,
                        is_allow=False,
                        account_id=None
                    )

                    # PermissionCategoryのidに基づいて、is_allowがFalseのtarget_idをdeny_targetsに追加する
                    permission_category = PermissionCategory.objects.filter(is_allow_filter).all()
                    for permission in permission_category:
                        deny_targets.append(permission.target_id)
                    # ライトプランではワークフローが使えない（したがって連絡先も不要になる）
                    if self.request.user.account.plan == Account.Plan.LIGHT:
                        deny_targets.extend([
                            PermissionTarget.Target.DISP_WORKFLOW_SETTING.value,
                            PermissionTarget.Target.DISP_CLIENT_SETTING.value
                        ])

                    allow_targets = list(set(all_targets) ^ set(deny_targets))
                    user_service.create_user_permissions(user, self.request.user, datetime_now, allow_targets, deny_targets)

                    # Userのpermission_category_idを書き換える
                    user.permission_category_id = permission_category_id
                    user.save()

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response = Response({'success': True}, status=status.HTTP_200_OK)

        # 編集したのが自分自身の場合はトークンの再発行をする
        if edit_user_id == user_id:
            user_service = UserService()
            response = user_service.add_new_token_headler(response, user)

        # メールを送る
        if user.type != User.Type.CLIENT.value:
            if edit_user_id:
                self.user_mailer.send_user_modify_mail(user, request.user)
            else:
                self.user_mailer.send_user_create_mail(user)

        return response


class UserDataListView(APIView):
    """
    汎用的な一覧
    画面表示に依存しない（ページネーション等を考慮しない）
    """

    def post(self, request):
        # request
        req_serializer = UserDataRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = req_serializer.data
        params['account'] = self.request.user.account_id

        user_service = UserService()
        user_list = user_service.get_user_list(params)

        res_serializer = UserDataResponseBodySerializer(user_list)
        return Response(data=res_serializer.data)


class UserClientCsvUpload(APIView):
    """
    連絡先ユーザ一括追加CSVアップロード
    """
    parser_classes = [FormParser, MultiPartParser]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def post(self, request: Union[Request, HttpRequest], client_id: int):
        try:
            client = Client.objects.get(
                id=client_id,
                provider_account=self.request.user.account,
                status=Client.Status.ENABLE.value,
            )
        except Client.DoesNotExist as e:
            logger.info(e)
            return Response({
                'success': False,
                'msg': 'パラメータが不正です',
            }, status=status.HTTP_400_BAD_REQUEST)

        csv_contents = request.data['csv'].read().decode('utf-8')
        importer = UserClientCsvImporter(contents=csv_contents, client=client, operated_by=self.request.user)
        try:
            if not importer.is_valid():
                return Response({
                    'success': False,
                    'msg': 'パラメータが不正です',
                    'errors': importer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
            importer.import_users()
        except UserClientCsvImporter.UserDuplicateError:
            return Response({
                'success': False,
                'msg': 'しばらく時間をおいてもう一度やり直してください',
            }, status=status.HTTP_409_CONFLICT)
        except Exception:
            return Response("エラーが発生しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'success': True})


class UserCsvUpload(APIView):
    """
    ユーザ一括追加CSVアップロード
    """
    parser_classes = [FormParser, MultiPartParser]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def post(self, request: Union[Request, HttpRequest]):

        csv_contents = request.data['csv'].read().decode('utf-8')
        importer = UserCsvImporter(contents=csv_contents, operated_by=self.request.user)
        try:
            if not importer.is_valid():
                return Response({
                    'success': False,
                    'msg': 'パラメータが不正です',
                    'errors': importer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
            importer.import_users()
        except UserCsvImporter.UserDuplicateError:
            return Response({
                'success': False,
                'msg': 'しばらく時間をおいてもう一度やり直してください',
            }, status=status.HTTP_409_CONFLICT)
        except Exception as ex:
            error_message = str(ex)
            stack_trace = traceback.format_exc()
            response_data = {
                'success': False,
                'msg': 'エラーが発生しました',
                'error_message': error_message,
                'stack_trace': stack_trace,
            }
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'success': True})


class UserPermissionsView(APIView):
    """
    自分の機能権限
    許可されている、されていないを含めて取得
    """

    def get(self, request):
        # request

        wheres = {
            'user': self.request.user,
            'status': Statusable.Status.ENABLE.value,
            'target__status': Statusable.Status.ENABLE.value
        }
        # ライトプランのときはワークフローと連絡先は常に不可
        plan_exclude = {
            'user__account__plan': Account.Plan.LIGHT.value,
            'target__id__in': [PermissionTarget.Target.DISP_WORKFLOW_SETTING.value,
                               PermissionTarget.Target.DISP_CLIENT_SETTING.value]
        }
        permissions = Permission.objects.select_related('target').exclude(**plan_exclude).filter(**wheres).all()

        res_serializer = UserPermissionsResponseBodySerializer(permissions)
        return Response(data=res_serializer.data)

    def post(self, request):
        req_serializer = UserPermissionsRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = req_serializer.data

        wheres_base = {
            'user_id': params.get('id'),
            'status': Statusable.Status.ENABLE.value,
            'target__status': Statusable.Status.ENABLE.value
        }
        permission_base = Permission.objects.select_related('target').filter(**wheres_base)
        now = make_aware(datetime.datetime.now())
        login_user = self.request.user

        permission_all = []
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
        return Response({"msg": ["設定しました"]}, status=status.HTTP_200_OK)


class UserPagePermissionCategoryView(APIView):
    """
    カテゴリーの一覧を表示
    """

    def get(self, request):
        # request
        login_user = self.request.user

        users_permissions = PermissionCategoryKey.objects.filter(
            Q(account=login_user.account) | Q(account__isnull=True),
        ).prefetch_related(
            Prefetch('permission_category_id',
                     queryset=PermissionCategory.objects.select_related('target').order_by('target__sort_id'),
                     to_attr='permissions')
        ).all()

        order_by = users_permissions.order_by("id")

        res_serializer = UserPermissionCategoryResponseBodySerializer(order_by)
        return Response(data=res_serializer.data)


class UserPermissionsListView(APIView):
    """
    全ユーザーの機能権限
    許可されている、されていないを含めて取得
    権限がまだついてないときは、不許可状態で付与する
    """

    def get(self, request):
        # request
        login_user = self.request.user
        wheres = {
            'account': login_user.account,
            'status': User.Status.ENABLE.value,
            'type': User.Type.ACCOUNT.value,
            'is_bpo': False,
        }
        permission_wheres = {
            'status': Statusable.Status.ENABLE.value,
            'target__status': Statusable.Status.ENABLE.value
        }
        users_permissions = User.objects.prefetch_related(
            Prefetch('permission_user',
                     queryset=Permission.objects.select_related('target').filter(**permission_wheres).order_by('target__sort_id'),
                     to_attr='permissions')).filter(
            **wheres).all()

        permission_targets = list(PermissionTarget.objects.filter(status=Statusable.Status.ENABLE.value).all())

        now = make_aware(datetime.datetime.now())
        modify_count = 0
        for user in users_permissions:
            user_permission_targets = []
            for permission in user.permissions:
                user_permission_targets.append(permission.target)
            # 権限設定自体が無い場合はこの場で作る
            lack_permission_targets = set(permission_targets) - set(user_permission_targets)
            lack_target_ids = []
            for target in lack_permission_targets:
                lack_target_ids.append(target.id)
            user_service = UserService()
            modify = user_service.create_user_permissions(user, login_user, now, [], lack_target_ids)
            modify_count += len(modify)

        if modify_count > 0:  # もう一度取り直す
            users_permissions = User.objects.prefetch_related(
                Prefetch('permission_user',
                         queryset=Permission.objects.select_related('target').filter(**permission_wheres),
                         to_attr='permissions')).filter(
                **wheres).all()
        res_serializer = UserPermissionsListResponseBodySerializer(list(users_permissions))
        return Response(data=res_serializer.data)


class UserPermissionCategorySetView(APIView):
    """
    ユーザーの権限処理
    """

    def post(self, request):
        req_serializer = UserPermissionsRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = req_serializer.data
        permission_id = params.get('permission_category_id')

        wheres_base = {
            'user_id': params.get('id'),
            'status': Statusable.Status.ENABLE.value,
            'target__status': Statusable.Status.ENABLE.value
        }
        permission_base = Permission.objects.select_related('target').filter(**wheres_base)
        now = make_aware(datetime.datetime.now())
        login_user = self.request.user
        permission_all = []
        user_id = params.get('id')
        try:
            user = User.objects.get(id=user_id)
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
            return Response({"msg": ["ユーザーが存在しません"]}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"msg": ["設定しました"]}, status=status.HTTP_200_OK)


class UserPermissionsCategoryListView(APIView):
    """
    カテゴリーのリスト
    """

    def get(self, request):
        # request
        login_user = self.request.user

        users_permissions = PermissionCategoryKey.objects.filter(
            Q(account=login_user.account) | Q(account__isnull=True),
        ).prefetch_related(
            Prefetch('permission_category_id',
                     queryset=PermissionCategory.objects.select_related('target').order_by('target__sort_id'),
                     to_attr='permissions')
        ).all()

        order_by = users_permissions.order_by("id")

        res_serializer = UserPermissionCategoryResponseBodySerializer(order_by)
        return Response(data=res_serializer.data)

    def post(self, request):
        req_serializer = UserPermissionCategoryRequestSerializer(data=request.data, many=True)  # `many=True` を追加
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params_list = req_serializer.data
        login_user = self.request.user

        wheres_base = {
            'status': Statusable.Status.ENABLE.value,
            'target__status': Statusable.Status.ENABLE.value,
            'account': login_user.account,
        }
        permission_base = PermissionCategory.objects.select_related('target').filter(**wheres_base)
        now = make_aware(datetime.datetime.now())

        permission_all = []
        permission_id_set = []
        try:
            for params in params_list:
                permission_category_id = params.get('id')
                if permission_category_id == 0:
                    # カテゴリーの新規作成
                    # PermissionCategoryオブジェクトを作成して保存する
                    new_permission_category = PermissionCategoryKey(
                        name=params['name'],
                        created_at=now,
                        updated_at=now,
                        account_id=login_user.account.id,
                        editing=1,
                        checked=0,
                        status=1,
                        # 追加の情報を指定するフィールドと値を追加する
                    )
                    new_permission_category.save()

                    # 新しく作成したPermissionCategoryオブジェクトのIDを取得
                    new_permission_category_id = new_permission_category.id

                    # PermissionCategoryKeyオブジェクトを新規作成して保存する
                    permissions = params.get('permissions')
                    for param_permission in permissions:
                        target_id = param_permission.get('target').get('id')
                        is_allow = param_permission.get('isAllow')
                        permission_key = PermissionCategory(
                            is_allow=is_allow,
                            status=1,
                            created_at=now,
                            updated_at=now,
                            created_by_id=login_user.id,
                            target_id=target_id,
                            updated_by_id=login_user.id,
                            account_id=login_user.account.id,
                            permission_category_id=new_permission_category_id,
                        )
                        permission_key.save()
                else:
                    # 既存カテゴリーのアップデート
                    permission_name = params.get('name')
                    permission_id = params.get('id')
                    permission_id_set.append(permission_id)

                    permission = PermissionCategoryKey.objects.get(id=permission_id)
                    permission.name = permission_name
                    permission.save()

                    wheres_category = {'permission_category_id': permission_category_id}
                    permission_category = permission_base.filter(**wheres_category).first()
                    if not permission_category:
                        return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

                    permissions = params.get('permissions')
                    for param_permission in permissions:
                        target_id = param_permission.get('target').get('id')
                        wheres_permission = {
                            'permission_category_id': permission_category_id,
                            'target_id': target_id
                        }
                        permission = permission_base.filter(**wheres_permission).first()
                        if not permission:
                            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

                        permission.is_allow = param_permission.get('isAllow')
                        if self.request.user.account.plan == Account.Plan.LIGHT.value:
                            if target_id in [PermissionTarget.Target.DISP_WORKFLOW_SETTING.value,
                                             PermissionTarget.Target.DISP_CLIENT_SETTING.value]:
                                permission.is_allow = False

                        permission.updated_by = login_user
                        permission.updated_at = now
                        permission_all.append(permission)

            PermissionCategory.objects.bulk_update(permission_all, fields=['is_allow', 'updated_by', 'updated_at'])
            for permission_id_for in permission_id_set:
                try:
                    user_id_serch = User.objects.filter(permission_category_id=permission_id_for)
                    for user_id_serch_id in user_id_serch:
                        permission_id = permission_id_for
                        wheres_base = {
                            'user_id': user_id_serch_id.id,
                            'status': Statusable.Status.ENABLE.value,
                            'target__status': Statusable.Status.ENABLE.value
                        }
                        permission_base = Permission.objects.select_related('target').filter(**wheres_base)
                        now = make_aware(datetime.datetime.now())
                        login_user = self.request.user
                        permission_all = []
                        user_id = user_id_serch_id.id
                        try:
                            User.objects.get(id=user_id)
                            try:
                                permission_category = PermissionCategory.objects.filter(
                                    permission_category_id=permission_id)
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
                                Permission.objects.bulk_update(permission_all,
                                                               fields=['is_allow', 'updated_by', 'updated_at'])
                            except DatabaseError as e:
                                logger.error(f"{e}: {traceback.format_exc()}")
                                return Response({"msg": ["DBエラーが発生しました"]},
                                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                        except User.DoesNotExist:
                            return Response({"msg": ["ユーザーが存在しません"]}, status=status.HTTP_400_BAD_REQUEST)
                except DatabaseError as e:
                    logger.error(f"{e}: {traceback.format_exc()}")
                    return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"msg": ["設定しました"]}, status=status.HTTP_200_OK)


class PermissionsCategoryDeleteView(APIView):
    def post(self, request, format=None):
        params_list = request.data
        login_user = self.request.user
        wheres_base = {
            'account': login_user.account,
        }
        try:
            for params in params_list:
                delete_category_id = params.get('id')
                if delete_category_id == 0:
                    continue
                categories_to_delete = PermissionCategory.objects.filter(
                    permission_category_id=delete_category_id).filter(**wheres_base)
                if not categories_to_delete:
                    return Response({"msg": ["PermissionCategoryエラー"]}, status=status.HTTP_400_BAD_REQUEST)
                keys_to_delete = PermissionCategoryKey.objects.filter(id=delete_category_id).filter(**wheres_base)
                if not keys_to_delete:
                    return Response({"msg": ["PermissionCategoryKeyエラー"]}, status=status.HTTP_400_BAD_REQUEST)
                # ユーザーが指定のpermission_category_idを使用している場合はエラーを返す
                if User.objects.filter(permission_category_id=delete_category_id).exists():
                    return Response({"msg": ["削除対象のカテゴリーが現在ユーザーによって使用されています"]},
                                    status=status.HTTP_400_BAD_REQUEST)

                # PermissionCategoryの削除
                categories_to_delete.delete()

                # PermissionCategoryKeyの削除
                keys_to_delete.delete()

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"msg": ["削除しました"]}, status=status.HTTP_200_OK)
