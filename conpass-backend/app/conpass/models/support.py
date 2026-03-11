from enum import Enum, unique
from django.db import models

from conpass.models.constants.statusable import Statusable


class Support(models.Model, Statusable):
    """
    サポート問い合わせ
    """
    @unique
    class Type(Enum):
        CONTRACT = 1  # 契約
        OPERATION = 2  # 操作
        ETC = 100  # その他全般

    @unique
    class Response(Enum):
        BEFORE_START = 0  # 未対応
        IN_PROCESS = 1  # 対応中
        FINISHED = 2  # 対応済

    TYPE_DISPLAYS = {
        Type.CONTRACT.value: "契約",
        Type.OPERATION.value: "操作",
        Type.ETC.value: "その他全般",
    }

    name = models.CharField(max_length=255)  # 問い合わせ件名
    body = models.TextField(max_length=2048)  # 問い合わせ本文
    type = models.IntegerField(default=Type.CONTRACT.value)  # 問い合わせ種別
    response = models.IntegerField(default=Response.BEFORE_START.value)  # 対応状況
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='support_created_by', blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='support_updated_by', blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.name

    def type_display(self) -> str:
        return self.TYPE_DISPLAYS[self.type]
