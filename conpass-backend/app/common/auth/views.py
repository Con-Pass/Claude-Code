from datetime import datetime, timedelta
import traceback
import pyotp
import rest_framework_jwt.views
from django.utils import timezone
from django.core.handlers.wsgi import WSGIRequest
from django.core.validators import EmailValidator
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.utils import jwt_response_payload_handler
from common.auth.serializer.social_login_serializer import SocialLoginRequestSerializer
from common.auth.serializer.sso_login_serializer import SsoLoginRequestSerializer
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError
from logging import getLogger
from conpass.mailer.mfa_mailer import MfaMailer

from conpass.models import User, Account, IpAddress
from conpass.models.login_failure import LoginFailure
from conpass.models.constants import Statusable, OtpInterval
from django.conf import settings

logger = getLogger(__name__)


def update_last_login(user: User):
    user.last_login = make_aware(datetime.now())
    user.save()


class LoginView(rest_framework_jwt.views.ObtainJSONWebToken):
    def post(self, request, *args, **kwargs):
        email = request.data['login_name']
        client_addr = self.get_client_ip(request)  # IPアドレス取得
        # login_nameがemailでない場合はエラー
        email_validator = EmailValidator()
        try:
            email_validator(email)
        except Exception as e:
            logger.info(e)
            return Response({"error_message": "不正なメールアドレス形式です。"}, status=status.HTTP_400_BAD_REQUEST)

        login_failure = self.get_login_failure(email)
        is_locked, lock_message = LoginFailure.check_lock_status(login_failure)
        if is_locked:
            return Response({'error_message': lock_message}, status=status.HTTP_400_BAD_REQUEST)

        """SameSiteを指定しただけで、他は継承元と同じ"""
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # ログイン成功時にLoginFailureをリセット
            if login_failure:
                login_failure.delete()

            user = serializer.object.get('user') or request.user
            token = serializer.object.get('token')

            # IPアドレス制限の確認
            if user.account.ipaddress_status:
                wheres = {
                    'ip_address': client_addr,
                    'account_id': user.account.id,
                    'status': Statusable.Status.ENABLE.value
                }
                is_whitelist = IpAddress.objects.filter(**wheres).exists()  # IPアドレスがホワイトリストに登録されているか
                count_wheres = {
                    'account_id': user.account.id,
                    'status': Statusable.Status.ENABLE.value
                }
                count_ip_address = IpAddress.objects.filter(**count_wheres).count()  # IPアドレスの登録数
                if not is_whitelist and count_ip_address > 0:
                    return Response({'error_message': 'ご利用環境のIPアドレスからのアクセスが許可されていません。'}, status=status.HTTP_400_BAD_REQUEST)

            # 利用者側画面はtype==ACCOUNT(顧客)以外のユーザ（連絡先、管理者）はログイン不可
            try:
                if User.objects.get(pk=user.id).type != User.Type.ACCOUNT.value:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                if User.objects.get(pk=user.id).account.status not in [Account.Status.ENABLE.value,
                                                                       Account.Status.PREPARE.value]:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                # 2段階認証用処理
                # one_time_passwordが存在しない場合エラーを返してメールを送信
                if User.objects.get(pk=user.id).account.mfa_status == Statusable.Status.ENABLE.value \
                   and User.objects.get(pk=user.id).mfa_status == Statusable.Status.ENABLE.value \
                   and 'one_time_password' not in request.data:
                    if not User.objects.get(pk=user.id).otp_secret:
                        return Response({"error_message": "ワンタイムパスワードの生成に失敗しました。\nシステム管理者にお問い合わせください。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    totp1 = self.generate_otp(user, OtpInterval.OtpIntervalTime.TIME300.value)
                    MfaMailer().send_otp_mail(user, totp1.now())
                    return Response({"error_message": "multi-factor-auth-required"}, status=status.HTTP_400_BAD_REQUEST)
                # one_time_passwordが存在する場合認証を行う
                if User.objects.get(pk=user.id).account.mfa_status == Statusable.Status.ENABLE.value \
                   and User.objects.get(pk=user.id).mfa_status == Statusable.Status.ENABLE.value \
                   and 'one_time_password' in request.data:
                    otp = request.data.get('one_time_password')
                    totp1 = self.generate_otp(user, OtpInterval.OtpIntervalTime.TIME300.value)
                    totp2 = self.generate_otp(user, OtpInterval.OtpIntervalTime.TIME30.value)
                    if not totp1.verify(otp) and not totp2.verify(otp):
                        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist as e:
                logger.info(e)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            response_data = jwt_response_payload_handler(token, user, request)
            response = Response(response_data)
            if api_settings.JWT_AUTH_COOKIE:
                frontend_env = request.headers.get("X-Frontend-Env")
                expiration = (datetime.utcnow() + api_settings.JWT_EXPIRATION_DELTA)
                if frontend_env == 'local':
                    response.set_cookie(api_settings.JWT_AUTH_COOKIE,
                                        token,
                                        expires=expiration,
                                        httponly=True,
                                        samesite='Lax',
                                        secure=False)  # SameSiteを指定

                else:
                    response.set_cookie(api_settings.JWT_AUTH_COOKIE,
                                        token,
                                        expires=expiration,
                                        httponly=True,
                                        samesite='None',
                                        domain='con-pass.jp',
                                        secure=True) # SameSiteを指定
            # 最終ログインを更新する
            update_last_login(user)
            return response
        else:
            self.handle_login_failure(email, login_failure)
            return Response({'error_message': 'idかパスワードが間違っています。'}, status=status.HTTP_400_BAD_REQUEST)

    def get_login_failure(self, email):
        try:
            return LoginFailure.objects.get(email=email)
        except LoginFailure.DoesNotExist:
            return None

    def handle_login_failure(self, email, login_failure):
        now = timezone.now()

        if login_failure is None:
            login_failure = LoginFailure(email=email, created_at=now, updated_at=now, count=1)
        else:
            login_failure.count += 1
            if login_failure.count == LoginFailure.LOCK_ATTEMPTS_COUNT:
                login_failure.lock_count += 1
            # LOCK_ATTEMPTS_COUNTをこえたらcountを1からにする
            elif login_failure.count > LoginFailure.LOCK_ATTEMPTS_COUNT:
                login_failure.count = 1
            login_failure.updated_at = now
        login_failure.save()

    def generate_otp(self, user: User, interval: int):
        otp_secret = User.objects.get(pk=user.id).otp_secret
        return pyotp.TOTP(otp_secret, interval=interval)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]  # X-Forwarded-For ヘッダーが使用されている場合（プロキシ経由の場合など）
        else:
            ip = request.META.get('REMOTE_ADDR')  # X-Forwarded-For ヘッダーが存在しない場合
        return ip


class SocialLoginView(rest_framework_jwt.views.ObtainJSONWebToken):
    def post(self, request, *args, **kwargs):
        """
        serializerを既存のJSONWebTokenSerializerから継承してvalidate内のログイン処理を変更
        uidを条件にUserを取得し、そのUserでログイン実行
        """
        self.serializer_class = SocialLoginRequestSerializer
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # userに紐づくsocial_loginのレコード更新
            try:
                social_login_data = serializer.object.get('social_login')
                datetime_now = make_aware(datetime.now())
                social_login_data.updated_at = datetime_now
                social_login_data.updated_by_id = serializer.object.get('user').id
                social_login_data.save()
            except DatabaseError as e:
                logger.error(f"{e}: {traceback.format_exc()}")
                return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # ログイン処理
            user = serializer.object.get('user') or request.user
            try:
                if User.objects.get(pk=user.id).status == User.Status.DISABLE.value:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                if User.objects.get(pk=user.id).account.status not in [Account.Status.ENABLE.value,
                                                                       Account.Status.PREPARE.value]:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            token = serializer.object.get('token')
            response_data = jwt_response_payload_handler(token, user, request)
            response = Response(response_data)
            if api_settings.JWT_AUTH_COOKIE:
                frontend_env = request.headers.get("X-Frontend-Env")
                expiration = (datetime.utcnow() + api_settings.JWT_EXPIRATION_DELTA)
                if frontend_env == 'local':
                    response.set_cookie(api_settings.JWT_AUTH_COOKIE,
                                        token,
                                        expires=expiration,
                                        httponly=True,
                                        samesite='Lax',
                                        secure=False)  # SameSiteを指定

                else:
                    response.set_cookie(api_settings.JWT_AUTH_COOKIE,
                                        token,
                                        expires=expiration,
                                        httponly=True,
                                        samesite='None',
                                        domain='con-pass.jp',
                                        secure=True) # SameSiteを指定
            # 最終ログインを更新する
            update_last_login(user)
            return response

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SsoLoginView(rest_framework_jwt.views.ObtainJSONWebToken):
    def post(self, request, *args, **kwargs):
        self.serializer_class = SsoLoginRequestSerializer
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # ログイン処理
            user = serializer.object.get('user') or request.user
            try:
                if User.objects.get(pk=user.id).status == User.Status.DISABLE.value:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                if User.objects.get(pk=user.id).account.status not in [Account.Status.ENABLE.value,
                                                                       Account.Status.PREPARE.value]:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            token = serializer.object.get('token')
            response_data = jwt_response_payload_handler(token, user, request)
            response = Response(response_data)
            if api_settings.JWT_AUTH_COOKIE:
                frontend_env = request.headers.get("X-Frontend-Env")
                expiration = (datetime.utcnow() + api_settings.JWT_EXPIRATION_DELTA)
                if frontend_env == 'local':
                    response.set_cookie(api_settings.JWT_AUTH_COOKIE,
                                        token,
                                        expires=expiration,
                                        httponly=True,
                                        samesite='Lax',
                                        secure=False)  # SameSiteを指定

                else:
                    response.set_cookie(api_settings.JWT_AUTH_COOKIE,
                                        token,
                                        expires=expiration,
                                        httponly=True,
                                        samesite='None',
                                        domain='con-pass.jp',
                                        secure=True) # SameSiteを指定
            # 最終ログインを更新する
            update_last_login(user)
            return response

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    def post(self, request: WSGIRequest):
        response = Response({
            'success': True
        })
        response.delete_cookie(api_settings.JWT_AUTH_COOKIE)
        return response
