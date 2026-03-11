from django.db import models
from conpass.models import Contract, User
from conpass.models.constants.statusable import Statusable
from django.db.models import UniqueConstraint


class ContractBody(models.Model, Statusable):
    """
    契約書の本文
    編集されるため、その時点での履歴の意味合いも含め溜まってゆく
    """
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, related_name='contract_body_contract')  # 契約書ID
    body = models.TextField()  # 契約書の本文
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='contract_body_created_by', blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='contract_body_updated_by', blank=True, null=True, default=None)  # 更新者
    is_adopted = models.BooleanField(default=False)  # 採用されているかどうか
    version = models.CharField(max_length=10, blank=True, null=True)  # 契約書バージョン名

    class Meta:
        constraints = [
            UniqueConstraint(fields=['contract', 'version'], name='unique_contract_version')
        ]

    def __str__(self):
        return self.contract.name + ' ' + self.updated_at.__str__()
