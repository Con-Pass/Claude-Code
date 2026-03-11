from django.db import models
from conpass.models import User, Account
from conpass.models.constants import ContractTypeable
from conpass.models.constants.statusable import Statusable


class Directory(models.Model, Statusable, ContractTypeable):
    """
    契約書などの階層構造
    種別（type）ごとに独立した階層構造を持ちます。
    見た目上の管理で、実データはこの階層構造になっているわけではない。
    ルート階層では契約書詳細などで表示するメタ情報の項目設定が出来る。
    """
    name = models.CharField(max_length=255)  # 名前
    level = models.IntegerField()  # 階層（0が最上位）
    parent = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='directory_parent',
                               blank=True, null=True, default=None)  # 親階層のID
    type = models.IntegerField(default=ContractTypeable.ContractType.CONTRACT.value)  # 種別（契約書／テンプレート／過去契約書）
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING,
                                related_name='directory_account', blank=True, null=True,
                                default=None)  # アカウント（一旦default=null）
    memo = models.CharField(max_length=255, blank=True, default="")  # 備考
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    sort_id = models.IntegerField(blank=True, null=True, default=None)
    keys = models.ManyToManyField("MetaKey", through="MetaKeyDirectory")
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='directory_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='directory_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.name
