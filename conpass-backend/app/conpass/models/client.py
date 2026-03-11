from django.db import models
from conpass.models import Account, Corporate
from conpass.models.constants.statusable import Statusable


class Client(models.Model, Statusable):
    """
    連絡先マスタ
    ConPass顧客から見た取引先
    基本的に契約書を交わす相手となる
    """
    name = models.CharField(max_length=255)  # 名前
    provider_account = models.ForeignKey(Account, on_delete=models.DO_NOTHING,
                                         related_name='client_provider_account',
                                         blank=True, null=True, default=None)  # 顧客ID（この連絡先から見ての顧客）
    corporate = models.ForeignKey(Corporate, on_delete=models.DO_NOTHING,
                                  related_name='client_corporate',
                                  blank=True, null=True, default=None)  # 法人ID（詳細情報はこちらで持つ）
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='client_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='client_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.name
