from django.db import models

from conpass.models import Contract, Workflow
from conpass.models.constants.statusable import Statusable


class AdobeSign(models.Model, Statusable):
    """
    AdobeSign連携情報
    agreement: 電子契約の手続き。 transientDocument か libraryDocument の契約書を必要とする。
    transientDocument: 電子契約のために一時的にアップロードされた契約書（pdf） １週間で消える
    libraryDocument: adobeSignで繰り返し使えるようにadobesign側に登録された契約書（pdf）
    adobesign側のidは数値ではなく、ランダム文字列になります
    """
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, related_name='adobesign_contract')
    workflow = models.ForeignKey(Workflow, on_delete=models.DO_NOTHING, related_name='adobesign_workflow', blank=True,
                                 null=True, default=None)  # ワークフローID
    agreement_id = models.CharField(max_length=512)  # adobesign の agreement.id
    transient_document_id = models.CharField(max_length=512, blank=True,
                                             null=True, default=None)  # adobesign の transientDocument.id
    library_document_id = models.CharField(max_length=512, blank=True,
                                           null=True, default=None)  # adobesign の libraryDocument.id
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='adobesign_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='adobesign_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.contract.name
