from rest_framework import serializers
from rest_framework_jwt.serializers import JSONWebTokenSerializer
from django.utils.translation import ugettext as _
from rest_framework_jwt.settings import api_settings
from conpass.models import User, SocialLogin, SsoLogin
from logging import getLogger

jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
jwt_decode_handler = api_settings.JWT_DECODE_HANDLER
jwt_get_username_from_payload = api_settings.JWT_PAYLOAD_GET_USERNAME_HANDLER
logger = getLogger(__name__)


class SsoLoginRequestSerializer(JSONWebTokenSerializer):
    def __init__(self, *args, **kwargs):
        super(JSONWebTokenSerializer, self).__init__(*args, **kwargs)
        self.fields[self.username_field] = serializers.CharField(allow_blank=True, required=False)
        self.fields['password'] = serializers.CharField(allow_blank=True, required=False)
        self.fields['reqId'] = serializers.CharField()
        self.fields['userId'] = serializers.CharField()

    def validate(self, attrs):
        ssoLogin = SsoLogin.objects.get(auth_request_id=attrs.get('reqId'))

        if ssoLogin:
            try:
                user = User.objects.get(id=attrs.get('userId'))
            except User.DoesNotExist as e:
                logger.info(e)
                raise serializers.ValidationError("ユーザが登録されていません")
        else:
            raise serializers.ValidationError("SSOログイン処理登録がされていません")

        # Userが存在すればログイン成功
        if user:
            if not user.is_active:
                msg = _('User account is disabled.')
                raise serializers.ValidationError(msg)

            payload = jwt_payload_handler(user)
            ssoLogin.delete()
            return {
                'token': jwt_encode_handler(payload),
                'user': user,
            }
        else:
            msg = _('Unable to log in with provided credentials.')
            raise serializers.ValidationError(msg)
