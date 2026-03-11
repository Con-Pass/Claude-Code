from django.db import models
from conpass.models import User, Group, PermissionTarget
from conpass.models.constants.statusable import Statusable


class Permission(models.Model, Statusable):
    """
    ユーザの権限設定
    各メニューや機能、画面単位での制限指定
    targetの機能が利用できるかどうか、という設定になる
    """
    target = models.ForeignKey(PermissionTarget, on_delete=models.DO_NOTHING, related_name='permisson_target',
                               blank=True, null=True, default=None)  # 権限指定対象
    is_allow = models.BooleanField()  # 許可する／しない
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='permission_user', blank=True, null=True,
                             default=None)  # ユーザID
    group = models.ForeignKey(Group, on_delete=models.DO_NOTHING, related_name='permission_group', blank=True,
                              null=True, default=None)  # グループID
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='permisson_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='permission_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.target.name + " " + self.user.username
