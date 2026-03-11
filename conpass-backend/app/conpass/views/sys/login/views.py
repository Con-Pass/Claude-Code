from datetime import datetime
import traceback
import rest_framework_jwt.views
from django.core.handlers.wsgi import WSGIRequest
from rest_framework import status
from rest_framework.response import Response
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.utils import jwt_response_payload_handler
from django.utils.timezone import make_aware
from logging import getLogger
from conpass.models.user import User
from conpass.views.sys.common import SysAPIView

logger = getLogger(__name__)


sys_cookie_name = 'auth-token-sys'


def update_last_login(user: User):
    user.last_login = make_aware(datetime.now())
    user.save()


class SysLoginView(rest_framework_jwt.views.ObtainJSONWebToken):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            user = serializer.object.get('user') or request.user
            token = serializer.object.get('token')
            # 管理画面はtype==3(ADMIN)のみログイン可能
            try:
                if User.objects.get(pk=user.id).type != User.Type.ADMIN.value:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist as e:
                logger.info(e)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            response_data = jwt_response_payload_handler(token, user, request)
            response = Response(response_data)
            if api_settings.JWT_AUTH_COOKIE:
                expiration = (datetime.utcnow() + api_settings.JWT_EXPIRATION_DELTA)
                response.set_cookie(sys_cookie_name,
                                    token,
                                    expires=expiration,
                                    httponly=True,
                                    samesite='Strict')  # SameSiteを指定
            # 最終ログインを更新する
            update_last_login(user)
            return response

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SysLogoutView(SysAPIView):
    def post(self, request: WSGIRequest):
        response = Response({
            'success': True
        })
        response.delete_cookie(sys_cookie_name)
        return response
