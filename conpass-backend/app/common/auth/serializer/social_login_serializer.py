from rest_framework import serializers
from rest_framework_jwt.serializers import JSONWebTokenSerializer
from rest_framework_jwt.settings import api_settings
from conpass.models import User, SocialLogin
from logging import getLogger

from conpass.models.constants import Statusable

jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
jwt_decode_handler = api_settings.JWT_DECODE_HANDLER
jwt_get_username_from_payload = api_settings.JWT_PAYLOAD_GET_USERNAME_HANDLER
logger = getLogger(__name__)


class SocialLoginRequestSerializer(JSONWebTokenSerializer):
    """
    Google,Microsoftログインの際、リクエストのuidからuserを取得してログイン
    親クラスのusername, passwordは不使用、firebase認証で取得するproviderId, uidを必須とする
    validateメソッドにuserのチェックを追加し、IDとパスワードの認証は削除（トークン取得部分は変更なし）
    """
    def __init__(self, *args, **kwargs):
        """
        Dynamically add the USERNAME_FIELD to self.fields.
        """
        super(JSONWebTokenSerializer, self).__init__(*args, **kwargs)
        self.fields[self.username_field] = serializers.CharField(allow_blank=True, required=False)
        self.fields['password'] = serializers.CharField(allow_blank=True, required=False)
        self.fields['providerId'] = serializers.CharField()
        self.fields['firebaseUid'] = serializers.CharField()
        self.fields['providerDataUid'] = serializers.CharField()

    def validate(self, attrs):
        # uidに紐づくUser取得
        wheres = {
            'provider_id': attrs.get('providerId'),
            'firebase_uid': attrs.get('firebaseUid'),
            'provider_data_uid': attrs.get('providerDataUid'),
            'status': Statusable.Status.ENABLE.value,
        }
        social_login_data = SocialLogin.objects.filter(**wheres).first()
        if social_login_data:
            try:
                user = User.objects.get(pk=social_login_data.user_id)
            except User.DoesNotExist as e:
                logger.info(e)
                raise serializers.ValidationError("アカウントと利用者が紐づいていません")
        else:
            raise serializers.ValidationError("アカウントが登録されていません")

        # Userが存在すればログイン成功
        if user:
            if not user.is_active:
                raise serializers.ValidationError("ユーザーアカウントが無効になっています")

            payload = jwt_payload_handler(user)

            return {
                'token': jwt_encode_handler(payload),
                'user': user,
                'social_login': social_login_data,
            }
        else:
            raise serializers.ValidationError("提供された認証情報でログインできません")
