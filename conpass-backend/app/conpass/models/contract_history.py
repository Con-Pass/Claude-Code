from django.db import models
from conpass.models import Contract, User
from conpass.models.constants.statusable import Statusable


class ContractHistory(models.Model, Statusable):
    """
    契約書の履歴
    contractは編集など変更がある度に複製を残し、ここで紐付けを行って履歴とする
    """
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING,
                                 related_name='contract_history_contract_id')  # 契約書ID
    contract_id_history = models.ForeignKey(Contract, on_delete=models.DO_NOTHING,
                                            related_name='contract_history_contract_id_history')  # 更新履歴上の契約書ID（その時点の契約書を複製したもの）
    name = models.CharField(max_length=255)  # 履歴の名前（便宜上のもの）
    revision = models.CharField(max_length=255)  # 履歴のリビジョン（便宜上のもの）
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='contract_history_created_by', blank=True, null=True,
                                   default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='contract_history_updated_by', blank=True, null=True,
                                   default=None)  # 更新者

    def __str__(self):
        return self.name
