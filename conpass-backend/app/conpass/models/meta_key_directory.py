from django.db import models
from conpass.models import User, Directory, MetaKey, Account
from conpass.models.constants.statusable import Statusable


class MetaKeyDirectory(models.Model, Statusable):
    """
    ディレクトリごとのメタ情報項目の表示可否
    """
    key = models.ForeignKey(MetaKey, on_delete=models.DO_NOTHING, related_name='meta_key_directory_key',
                            blank=True, null=True, default=None)   # key
    directory = models.ForeignKey(Directory, on_delete=models.DO_NOTHING, related_name='meta_key_directory_directory',
                                  blank=True, null=True, default=None)  # 階層ID（指定無しは全体設定）
    is_visible = models.BooleanField()  # 表示（true/false）
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING,
                                related_name='meta_key_directory_account', blank=True, null=True,
                                default=None)  # アカウント（一旦default=null）
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='meta_key_directory_created_by',
                                   blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='meta_key_directory_updated_by',
                                   blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return str(self.key) + '-' + str(self.directory)
