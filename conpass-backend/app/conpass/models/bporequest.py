from enum import Enum, unique
from django.db import models

from conpass.models.constants.statusable import Statusable


class BPORequest(models.Model, Statusable):
    """
    BPO依頼
    """

    class Type(Enum):
        PURCHASE_BOX = 1  # 原本保管箱購入
        COLLECT = 2  # 原本回収
        SCAN = 3  # 原本スキャン
        DESTRUCT = 4  # 原本廃棄
        TAKEOUT = 5  # 原本取り出し

    class Response(Enum):
        BEFORE_START = 0  # 未対応
        IN_PROCESS = 1  # 作業中
        FINISHED = 2  # 対応済

    TYPE_DISPLAYS = {
        Type.PURCHASE_BOX.value: "保存箱のご注文",
        Type.COLLECT.value: "原本の回収依頼",
        Type.SCAN.value: "原本スキャン依頼",
        Type.DESTRUCT.value: "原本廃棄依頼",
        Type.TAKEOUT.value: "原本取り出し依頼",
    }

    name = models.CharField(max_length=255)
    body = models.TextField(max_length=2048)
    type = models.IntegerField(default=Type.PURCHASE_BOX.value)
    response = models.IntegerField(default=Response.BEFORE_START.value)  # 対応状況
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='bpo_created_by', blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='bpo_updated_by', blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.name

    def type_display(self) -> str:
        return self.TYPE_DISPLAYS[self.type]
