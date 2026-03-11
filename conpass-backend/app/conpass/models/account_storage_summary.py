from enum import Enum

from django.db import models
from conpass.models import Account


class AccountStorageSummary(models.Model):
    """
    GCSの利用容量ログ
    一定間隔ごとに溜めてゆく
    ファイル情報はDBのFileから取得
    """

    class Cycle(Enum):
        DAILY = 'daily'
        MONTHLY = 'monthly'

    CYCLE_CHOICES = (
        ('daily', 'daily'),
        ('monthly', 'monthly'),
    )

    account = models.ForeignKey(Account, on_delete=models.CASCADE)  # 顧客ID
    file_size_total = models.BigIntegerField()  # 最大ファイルサイズ合計
    file_num = models.IntegerField()  # ファイルサイズが最大時のファイル数
    cycle = models.CharField(max_length=20, choices=CYCLE_CHOICES)  # 集計間隔
    date_from = models.DateField()  # 集計日時
    date_to = models.DateField()  # 集計日時
    created_at = models.DateTimeField(auto_now_add=True)  # 登録日時
    updated_at = models.DateTimeField(auto_now=True)  # 更新日時

    class Meta:
        unique_together = [
            ("account", "cycle", "date_from"),
        ]

    def __str__(self):
        return self.account.name + " " + self.created_at.__str__()
