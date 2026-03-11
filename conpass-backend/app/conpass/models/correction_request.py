from enum import Enum, unique
from django.db import models

from conpass.models import Contract, Workflow, User
from conpass.models.constants.statusable import Statusable


class CorrectionRequest(models.Model, Statusable):
    """
    データ補正依頼
    """
    @unique
    class Type(Enum):
        CORRECTION = 11  # データ補正
        BPO_DELEGETED_STAMP = 21  # 代理押印
        BPO_DELEGATED_RECEIPT = 22  # 代理受取

    @unique
    class Response(Enum):
        BEFORE_START = 0  # 未対応
        IN_PROCESS = 1  # 対応中
        FINISHED = 2  # 対応済

    TYPE_DISPLAYS = {
        Type.CORRECTION.value: "データ補正",
        Type.BPO_DELEGETED_STAMP.value: "代理押印",
        Type.BPO_DELEGATED_RECEIPT.value: "代理受取"
    }

    name = models.CharField(max_length=255)
    body = models.TextField(max_length=2048)
    type = models.IntegerField(default=Type.CORRECTION.value)
    response = models.IntegerField(default=Response.BEFORE_START.value)  # 対応状況
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, related_name='correction_request_contract')  # 契約書ID
    workflow = models.ForeignKey(Workflow, on_delete=models.DO_NOTHING,
                                 related_name='correction_request_workflow', blank=True, null=True, default=None)  # ワークフローID
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='correction_request_created_by', blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='correction_request_updated_by', blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.name

    def type_display(self) -> str:
        return self.TYPE_DISPLAYS[self.type]
