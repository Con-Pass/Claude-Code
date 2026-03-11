import datetime

from django.db import models
from django.utils.timezone import make_aware

from conpass.models.constants.statusable import Statusable
from conpass.models import Account, User, MetaKey



class CompanyMetaKey(models.Model, Statusable):
    """
    メタ情報の項目管理
    NaturalLanguageで読み取るラベルと、ユーザが任意に設定できる名前がある
    ディレクトリ単位で指定が可能
    デフォルト項目は編集できないが、表示有無は指定できる
    """


    is_visible = models.BooleanField(null=True)  # 表示（true/false）
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING, related_name='company_meta_key_account',
                                blank=True, null=True, default=None)  # アカウントID
    meta_key= models.ForeignKey(MetaKey, on_delete=models.DO_NOTHING, related_name='company_meta_key_meta_key', null=True)

    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField(null=True)  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='company_meta_key_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField(null=True)  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='company_meta_key_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.status
