from enum import Enum
from django.db import models
from conpass.models import Account, User
from conpass.models.constants import Statusable
from conpass.models.constants.typeable import Typeable


class LeaseKey(models.Model, Statusable):
    class Type(Enum):
        DEFAULT = Typeable.Type.DEFAULT.value
        FREE = Typeable.Type.FREE.value

    name=models.CharField(max_length=255)
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING, related_name='lease_key_account',
                                blank=True, null=True, default=None)  # アカウントID
    type = models.IntegerField(default=Type.FREE.value)
    is_visible = models.BooleanField()  # 表示（true/false）
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='lease_key_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='lease_key_updated_by', blank=True,
                                   null=True, default=None)  # 更新者


    def __str__(self):
        return self.name
