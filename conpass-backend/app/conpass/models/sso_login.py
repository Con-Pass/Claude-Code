from django.db import models
from conpass.models.constants.statusable import Statusable


class SsoLogin(models.Model, Statusable):
    """
    SSOログイン時の一時的保存
    """

    auth_request_id = models.CharField(max_length=255, null=True)  # SSOでの認証リクエストID
    user_id = models.CharField(max_length=255, null=True)  # SSO側のユーザID
    org_id = models.CharField(max_length=6)  # 組織ID
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


def __str__(self):
    return self.name
