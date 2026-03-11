from django.db import models
from conpass.models import Contract, User
from conpass.models.constants.statusable import Statusable


class ContractArchive(models.Model, Statusable):
    """
    条文アーカイブ
    """

    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING,
                                 related_name='contract_archive_contract')  # 契約書ID
    body_text = models.TextField()  # 条文
    reason = models.CharField(max_length=128)  # 修正理由
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='contract_archive_created_by',
                                   blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='contract_archive_updated_by',
                                   blank=True, null=True, default=None)  # 更新者
