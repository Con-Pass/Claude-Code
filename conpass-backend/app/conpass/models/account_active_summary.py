from enum import Enum

from django.db import models

from conpass.models import Account


class AccountActiveSummary(models.Model):
    """
    アカウントアクティブ契約数
    一定間隔ごとに溜めてゆく
    """

    class Cycle(Enum):
        DAILY = 'daily'
        MONTHLY = 'monthly'

    CYCLE_CHOICES = (
        ('daily', 'daily'),
        ('monthly', 'monthly'),
    )

    account = models.ForeignKey(Account, on_delete=models.CASCADE)  # 顧客ID
    active_contracts_count = models.IntegerField()  # 最大アクティブ契約数
    cycle = models.CharField(max_length=20, choices=CYCLE_CHOICES, default=Cycle.DAILY)  # 集計間隔
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
