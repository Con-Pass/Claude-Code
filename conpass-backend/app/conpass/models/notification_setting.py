from enum import Enum, unique
from django.db import models
from conpass.models import User
from conpass.models.constants.statusable import Statusable


class NotificationSetting(models.Model, Statusable):
    """
    通知設定のテーブル
    """

    @unique
    class Type(Enum):
        WORKFLOW = 1  # ワークフロー
        CONTRACT_DEADLINE = 2  # 契約書期限
        CONTRACT_MONTH = 3  # 今月の契約

    name = models.CharField(max_length=255)  # 名前
    type = models.IntegerField(default=Type.WORKFLOW.value)  # 種別（ワークフロー／契約書期限／今月の契約）
    info = models.BooleanField()  # お知らせ
    mail = models.BooleanField()  # メール
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='notification_setting_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='notification_setting_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.name
