from django.db import models
from conpass.models import User, Directory, Group
from conpass.models.constants.statusable import Statusable


class DirectoryPermission(models.Model, Statusable):
    """
    各ディレクトリへのユーザごとのアクセス権限
    グループ単位で指定されている場合はグループIDが入る
    テンプレートは基本的にアクセス制限しない（全部見られる）
    """
    directory = models.ForeignKey(Directory, on_delete=models.DO_NOTHING,
                                  related_name='directory_permission_directory')  # ディレクトリID
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='directory_permission_user',
                             blank=True, null=True, default=None)  # 対象ユーザID
    group = models.ForeignKey(Group, on_delete=models.DO_NOTHING,
                              related_name='directory_permission_group', blank=True, null=True, default=None)  # グループID
    is_visible = models.BooleanField()  # 表示（true/false）
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='directory_permission_created_by', blank=True, null=True,
                                   default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='directory_permission_updated_by', blank=True, null=True,
                                   default=None)  # 更新者

    def __str__(self):
        return self.directory.name
