from django.db import models

from conpass.models import Account, User
from conpass.models.constants.statusable import Statusable


class AdobeSetting(models.Model, Statusable):
    """
    AdobeSignのauth認証情報
    """
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING,
                                related_name='adobe_setting_account', blank=True, null=True,
                                default=None)  # 顧客（アカウント）ID typeが顧客の場合
    application_id = models.CharField(max_length=255, default='')  # adobesign の アプリケーションID
    client_secret = models.CharField(max_length=255, default='')  # adobesign の アプリケーションシークレット
    access_token = models.CharField(max_length=255)  # adobesign の アクセストークン
    refresh_token = models.CharField(max_length=255)  # adobesign の リフレッシュトークン
    expires_in = models.IntegerField()  # アクセストークンが有効な秒数
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='adobe_setting_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='adobe_setting_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.account.name
