import datetime
import traceback
from logging import getLogger
import pyotp

from django.contrib.auth.hashers import make_password
from django.db.utils import DatabaseError
from django.utils.timezone import make_aware
from rest_framework import status
from rest_framework.response import Response

from conpass.mailer.user_mailer import UserMailer
from conpass.models import User, Corporate, Client, Account, PermissionTarget
from conpass.models.constants import Statusable
from conpass.services.user.user_service import UserService
from conpass.views.sys.common import SysAPIView
from conpass.views.sys.user.serializer.user_detail_serializer import UserDetailRequestBodySerializer, \
    UserDetailResponseBodySerializer
from conpass.views.sys.user.serializer.user_edit_serializer import UserEditRequestBodySerializer
from conpass.views.sys.user.serializer.user_serializer import UserRequestBodySerializer, \
    UserResponseBodySerializer, UserDeleteRequestBodySerializer
from conpass.views.sys.user.serializer.user_type_list_serializer import \
    UserViewListResponseBodySerializer

logger = getLogger(__name__)


class SysUserListView(SysAPIView):

    def get(self, request):
        # request
        req_serializer = UserRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wheres = {
            'status': User.Status.ENABLE.value,
            'is_bpo': False
        }
        if req_serializer.data.get('userName'):
            wheres['username__contains'] = req_serializer.data.get('userName')

        # query
        user_list = list(User.objects.filter(**wheres).order_by('account', 'username').all())

        # response
        res_serializer = UserResponseBodySerializer(user_list)
        return Response(data=res_serializer.data)


class SysUserDeleteView(SysAPIView):

    def post(self, request):

        req_serializer = UserDeleteRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = request.data
        user = self.request.user
        result_list = []

        user_service = UserService()
        now = make_aware(datetime.datetime.now())
        for delete_id in list(params['ids']):
            try:
                delete_user = User.objects.get(
                    pk=delete_id
                )
            except User.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
            user_service.delete_user_data(delete_user, user, now)
            result_list.append(delete_id)

        return Response(data=result_list)


class SysBPOUserDetailView(SysAPIView):

    def get(self, request):
        req_serializer = UserDetailRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        account_id = req_serializer.data.get('id')  # ここでのIDはaccountID

        if account_id:
            try:
                # BPOユーザは基本的に１人だけ
                user = User.objects.get(account_id=account_id, is_bpo=True, status=User.Status.ENABLE.value)
            except User.DoesNotExist as e:
                logger.info(e)
                user = User()
        else:
            user = User()

        res_serializer = UserDetailResponseBodySerializer(user)
        return Response(data=res_serializer.data)


class SysUserDetailView(SysAPIView):

    def get(self, request):
        req_serializer = UserDetailRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user_id = req_serializer.data.get('id')

        if user_id:
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            user = User()

        res_serializer = UserDetailResponseBodySerializer(user)
        return Response(data=res_serializer.data)


class SysUserEditView(SysAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.user_mailer = UserMailer()

    def post(self, request):
        req_serializer = UserEditRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        edit_user_id = req_serializer.data.get('id')  # 編集対象（無い時は新規作成）
        user_id = self.request.user.id  # 操作している人
        datetime_now = make_aware(datetime.datetime.now())
        login_name = req_serializer.data.get('loginName')

        # 重複チェック
        if User.objects.exclude(pk=edit_user_id).filter(login_name=login_name).count() > 0:
            return Response({"msg": ["ログインIDが重複しています。"]}, status=status.HTTP_400_BAD_REQUEST)

        if edit_user_id:
            try:
                user = User.objects.get(pk=edit_user_id)
            except User.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            user = User()

        try:
            user.login_name = login_name

            # 更新時はパスワードが入力された場合のみ更新
            if req_serializer.data.get('inputPassword'):
                user.password = make_password(req_serializer.data.get('inputPassword'))

            user.username = req_serializer.data.get('username')
            user.division = req_serializer.data.get('division')
            user.position = req_serializer.data.get('position')
            user.email = req_serializer.data.get('email')
            user.tel = req_serializer.data.get('tel')
            user.memo = req_serializer.data.get('memo')
            user.status = req_serializer.data.get('status')
            user.mfa_status = req_serializer.data.get('mfaStatus')
            user.type = req_serializer.data.get('type')
            user.is_bpo = req_serializer.data.get('isBpo')
            user.is_bpo_admin = req_serializer.data.get('isBpoAdmin')
            if not edit_user_id:
                user.created_by_id = user_id
                user.created_at = datetime_now
                user.otp_secret = pyotp.random_base32()
            user.updated_by_id = user_id
            user.updated_at = datetime_now
            # 権限設定が顧客の場合
            if req_serializer.data.get('type') == User.Type.ACCOUNT.value:
                user.account_id = req_serializer.data.get('accountId')
                user.corporate_id = req_serializer.data.get('corporateId')
            # 権限設定が取引先の場合
            elif req_serializer.data.get('type') == User.Type.CLIENT.value:
                user.client_id = req_serializer.data.get('clientId')
                user.corporate_id = req_serializer.data.get('corporateId')
            user.save()

            # 通常ユーザの新規作成時は権限設定もあわせて行う
            if not edit_user_id and user.type == User.Type.ACCOUNT.value:
                user_service = UserService()
                # ユーザ管理だけ不許可
                all_targets = [target.value for target in PermissionTarget.Target]
                deny_targets = [PermissionTarget.Target.DISP_USER_SETTING.value]
                # ライトプランではワークフローが使えない（したがって連絡先も不要になる）
                if user.account.plan == Account.Plan.LIGHT:
                    deny_targets.extend(
                        [PermissionTarget.Target.DISP_WORKFLOW_SETTING.value,
                         PermissionTarget.Target.DISP_CLIENT_SETTING.value]
                    )
                allow_targets = list(set(all_targets) ^ set(deny_targets))
                user_service.create_user_permissions(user, self.request.user, datetime_now, allow_targets, deny_targets)

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response = Response(status=status.HTTP_200_OK)

        # 編集したのが自分自身の場合はトークンの再発行をする
        if edit_user_id == user_id:
            user_service = UserService()
            response = user_service.add_new_token_headler(response, user, 'auth-token-sys')

        # メールを送る
        if user.type != User.Type.CLIENT.value:
            if edit_user_id:
                self.user_mailer.send_user_modify_mail(user, request.user)
            else:
                self.user_mailer.send_user_create_mail(user)

        return response


class SysUserTypeListView(SysAPIView):

    def get(self, request):
        # account
        account = Account.objects.filter(status=Account.Status.ENABLE.value)

        # client
        client = Client.objects.filter(status=Client.Status.ENABLE.value)

        # corporate
        corporate = Corporate.objects.filter(status=Corporate.Status.ENABLE.value)

        data = {
            'account_list': list(account),
            'client_list': list(client),
            'corporate_list': list(corporate),
        }

        res = UserViewListResponseBodySerializer(data)
        return Response(data=res.data)
