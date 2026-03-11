from django.db import models
from conpass.models import User, Group, PermissionTarget, PermissionCategoryKey, Account

from conpass.models.constants.statusable import Statusable


class PermissionCategory(models.Model, Statusable):
    """
    権限カテゴリ設定
    各メニューや機能、画面単位での制限指定
    targetの機能が利用できるかどうか、という設定になる
    """
    target = models.ForeignKey(PermissionTarget, on_delete=models.DO_NOTHING, related_name='permisson_category_target',
                               blank=True, null=True, default=None)  # 権限指定対象
    is_allow = models.BooleanField()  # 許可する／しない
    permission_category = models.ForeignKey(PermissionCategoryKey, on_delete=models.DO_NOTHING,
                                            related_name='permission_category_id', blank=True,
                                            null=True, default=None)  # 権限ID
    group = models.ForeignKey(Group, on_delete=models.DO_NOTHING, related_name='permission_category_group', blank=True,
                              null=True, default=None)  # グループID
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='permisson_category_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='permission_category_updated_by', blank=True,
                                   null=True, default=None)  # 更新者
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING, related_name='permission_category_account',
                                blank=True, null=True, default=None)  # アカウントID
