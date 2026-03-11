from config.settings import *
from config.settings import LOGGING

DEBUG = True

LOGGING["loggers"]["faker"] = {
    'level': 'INFO',
}

LOGGING["loggers"]["factory"] = {
    'level': 'INFO',
}

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'common.auth.authentication.JSONWebTokenAuthenticationUserLogin',
        # システム管理側画面のcookieを分けるため認証を上記で分割
        # 'rest_framework_jwt.authentication.JSONWebTokenAuthentication',
        # 'rest_framework.authentication.SessionAuthentication',
        # 'rest_framework.authentication.BasicAuthentication',
        # 'rest_framework.authentication.TokenAuthentication',
    ),
    'JWT_AUTH_COOKIE': 'auth-token',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}
