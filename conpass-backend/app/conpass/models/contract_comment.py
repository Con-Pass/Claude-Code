from django.db import models
from conpass.models import Contract, User
from conpass.models.constants.statusable import Statusable


class ContractComment(models.Model, Statusable):
    """
    契約書のコメント
    各契約書に紐付く
    """
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, related_name='contract_comment_contract')  # 契約書ID
    linked_version = models.IntegerField()  # コメントが紐付いているバージョン(整数)
    comment = models.TextField(default="")  # コメント
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='contract_comment_created_by', blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='contract_comment_updated_by', blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.contract.name + ' ' + self.updated_at.__str__()
