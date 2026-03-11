import traceback
import json
from logging import getLogger

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from conpass.views.account.serializer.account_link_serializer import AccountLinkRequestBodySerializer
from conpass.views.account.serializer.account_idp_settings_serializer import AccountIdpSettingsRequestBodySerializer
from conpass.models import SocialLogin, User, Account
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError
import datetime
from django.conf import settings

logger = getLogger(__name__)


class AccountLinkView(APIView):

    def post(self, request):

        req_serializer = AccountLinkRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = req_serializer.data
        datetime_now = make_aware(datetime.datetime.now())
        try:
            user = User.objects.get(pk=params.get("userId"))
        except User.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # user_id, proveder_idを条件にレコードを検索
            sociallogin = SocialLogin.objects \
                .filter(user_id=params.get('userId'), provider_id=params.get('providerId')).first()
            if sociallogin:
                # 更新
                sociallogin.access_token = params.get('accessToken')
                sociallogin.refresh_token = params.get('refreshToken')
                sociallogin.firebase_uid = params.get('firebaseUid')
                sociallogin.provider_data_uid = params.get('providerDataUid')
                sociallogin.photo_url = params.get('photoUrl')
                sociallogin.ms_photo_data = params.get('msPhotoData')
                sociallogin.updated_by_id = params.get('userId')
                sociallogin.updated_at = datetime_now
            else:
                # 新規登録
                sociallogin = SocialLogin(
                    user_id=params.get('userId'),
                    access_token=params.get('accessToken'),
                    refresh_token=params.get('refreshToken'),
                    client_id=user.client.id if user.client else 0,
                    type=SocialLogin.Type.GOOGLE.value if params.get(
                        'providerId') == 'google.com' else SocialLogin.Type.MICROSOFT.value,
                    provider_id=params.get('providerId'),
                    firebase_uid=params.get('firebaseUid'),
                    provider_data_uid=params.get('providerDataUid'),
                    photo_url=params.get('photoUrl'),
                    ms_photo_data=params.get('msPhotoData'),
                    status=SocialLogin.Status.ENABLE.value,
                    created_by_id=params.get('userId'),
                    created_at=datetime_now,
                    updated_by_id=params.get('userId'),
                    updated_at=datetime_now,
                )
            sociallogin.save()
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)


class AccountSpSettingsView(APIView):

    # 現状SP情報はアカウント毎に設定されることは無いが、今後アカウント毎に異なる設定が追加される可能性を
    # 考慮してアカウントレベルで設定情報を取得するAPIとしておく
    def get(self, request):
        user=request.user
        org_id=user.account.org_id
        base_url = f"{settings.SSO_SAML_BASE_URL}/{org_id}"
        sp_settings ={
                'spEntityId': f"{base_url}/metadata/",
                'acsUrl': f"{base_url}/acs/",
                'acsBinding': "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                'slsUrl': f"{base_url}/sls/",
                'slsBinding': "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                'nameIdFormat':"urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
        }
        return Response(data=sp_settings)


class AccountIdpSettingsView(APIView):

    def get(self, request):
        user = self.request.user
        try:
            account = Account.objects.get(pk=user.account_id)
        except Account.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["アカウントが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        response = json.loads(account.idp_settings) if account.idp_settings else {}

        return Response(response)

    def put(self, request):
        req_serializer = AccountIdpSettingsRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = req_serializer.data
        if params.get('idpEntityId') and params.get('singleSignOnUrl') and params.get('x509Certificate'):
            settings = {
                'idpEntityId': params.get('idpEntityId'),
                'singleSignOnUrl': params.get('singleSignOnUrl'),
                'x509Certificate': params.get('x509Certificate')
            }
        else:
            settings = None

        user = self.request.user
        try:
            account = Account.objects.get(pk=user.account_id)
            account.idp_settings = json.dumps(settings) if settings is not None else None
            account.save()
        except Account.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["アカウントが見つかりません"]}, status=status.HTTP_404_NOT_FOUND)

        return Response(settings)
