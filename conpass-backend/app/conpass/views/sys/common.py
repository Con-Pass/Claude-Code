from rest_framework.generics import ListAPIView
from rest_framework.views import APIView

from common.auth.authentication import JSONWebTokenAuthenticationSysLogin


class SysAPIView(APIView):
    authentication_classes = [
        JSONWebTokenAuthenticationSysLogin,
    ]


class SysListAPIView(ListAPIView):
    authentication_classes = [
        JSONWebTokenAuthenticationSysLogin,
    ]
