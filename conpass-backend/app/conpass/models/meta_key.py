from enum import Enum, unique
from django.db import models
from conpass.models import User, Account, Directory
from conpass.models.constants.statusable import Statusable
from conpass.models.constants.typeable import Typeable


class MetaKey(models.Model, Statusable):
    """
    メタ情報の項目管理
    NaturalLanguageで読み取るラベルと、ユーザが任意に設定できる名前がある
    ディレクトリ単位で指定が可能
    デフォルト項目は編集できないが、表示有無は指定できる
    """

    class Type(Enum):
        # 関連のないモデル（contract）から参照可能にするためTypeableを継承
        DEFAULT = Typeable.Type.DEFAULT.value
        FREE = Typeable.Type.FREE.value

    name = models.CharField(max_length=255)  # 名前
    label = models.CharField(max_length=255, default='')  # NaturalLanguage でのラベル名 companya など
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING, related_name='meta_key_account',
                                blank=True, null=True, default=None)  # アカウントID
    type = models.IntegerField(default=Type.FREE.value)  # 種別（デフォルト／自由）
    is_visible = models.BooleanField()  # 表示（true/false）
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='meta_key_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='meta_key_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.name
