from django.db import models
from conpass.models import Account
from conpass.models.constants.statusable import Statusable


class IpAddress(models.Model):
    """
    IPアドレス制限の為のマスタ
    顧客毎にアクセスを許可するIPアドレスを登録する
    """
    ip_address = models.CharField(max_length=255)  # IPアドレス
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING, related_name='ip_address_account',
                                blank=True, null=True, default=None)  # アカウントID
    remarks = models.CharField(max_length=255)  # 備考
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='ip_address_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='ip_address_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.ip_address
