from django.db import models
from conpass.models import Account
from conpass.models.constants.statusable import Statusable


class Group(models.Model, Statusable):
    """
    ユーザのグループ
    ユーザとグループは多対多の関係
    """
    name = models.CharField(max_length=255)  # グループ
    description = models.CharField(max_length=255)  # 説明
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING,
                                related_name='group_account', blank=True, null=True,
                                default=None)  # アカウント（一旦default=null）
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING, related_name='group_created_by',
                                   blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING, related_name='group_updated_by',
                                   blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.name
