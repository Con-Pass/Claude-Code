from rest_framework_jwt.authentication import JSONWebTokenAuthentication

SYS_COOKIE_NAME = 'auth-token-sys'


class JSONWebTokenAuthenticationUserLogin(JSONWebTokenAuthentication):
    """
    settingの'DEFAULT_AUTHENTICATION_CLASSES'に追加
    ユーザ側画面のシステム管理側を分けるため
    """
    def get_jwt_value(self, request):
        return super().get_jwt_value(request)


class JSONWebTokenAuthenticationSysLogin(JSONWebTokenAuthentication):
    """
    システム管理でログインした場合cookie名が変わるためユーザ向けとは別に認証を判定する
    cookie取得部分のみオーバーライド
    """
    def get_jwt_value(self, request):
        if request.COOKIES.get(SYS_COOKIE_NAME):
            return request.COOKIES.get(SYS_COOKIE_NAME)
        else:
            return None
