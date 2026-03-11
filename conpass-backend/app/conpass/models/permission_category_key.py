from django.db import models
from conpass.models.constants.statusable import Statusable
from conpass.models import Account


class PermissionCategoryKey(models.Model, Statusable):
    """
    ユーザの権限の項目名マスタ
    "契約書閲覧"であれば、契約書の閲覧をする機能がすべて対象になる
    """
    name = models.CharField(max_length=255)  # 権限名
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    updated_at = models.DateTimeField()  # 更新日時
    editing = models.BooleanField(default=True)  # 編集できる/できない
    checked = models.BooleanField(default=False)  # チェック確認
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING, related_name='permission_category_key_account',
                                blank=True, null=True, default=None)  # アカウントID

    def __str__(self):
        return self.name
