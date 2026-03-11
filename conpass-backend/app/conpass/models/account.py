from enum import Enum
from django.db import models
from conpass.models.constants.statusable import Statusable


class Account(models.Model, Statusable):
    """
    顧客マスタ
    ConPassとの契約
    """

    class Plan(Enum):
        LIGHT = 1
        STANDARD = 2
        STANDARD_PLUS = 3

    class PlanDisplayName(Enum):
        LIGHT = 'ライト'
        STANDARD = 'スタンダード'
        STANDARD_PLUS = 'スタンダード・プラス'

    class Status(Enum):
        """
        アカウントのステータスには「停止」がある。
        未入金状態など、解約にはなっていないが一時的に使えないような状態
        Enumを継承したクラスはサブクラスが作れないのでここは個別に指定
        """
        DISABLE = 0
        ENABLE = 1
        SUSPEND = 10
        PREPARE = 20

    class StatusDisplayName(Enum):
        DISABLE = '無効'
        ENABLE = '有効'
        SUSPEND = '停止'
        PREPARE = '準備中'

    class WfBpoTaskDelegatedStampStatus(Enum):
        DISABLE = 0
        ENABLE = 1

    class WfBpoTaskDelegatedStampStatusDisplayName(Enum):
        DISABLE = '無効'
        ENABLE = '有効'

    class WfBpoTaskDelegatedReceiptStatus(Enum):
        DISABLE = 0
        ENABLE = 1

    class WfBpoTaskDelegatedReceiptStatusDisplayName(Enum):
        DISABLE = '無効'
        ENABLE = '有効'

    class SsoStatus(Enum):
        DISABLE = 0
        ENABLE = 1

    class SsoStatusDisplayName(Enum):
        DISABLE = '無効'
        ENABLE = '有効'

    name = models.CharField(max_length=255)  # 名前
    plan = models.IntegerField(default=Plan.LIGHT.value)  # 契約プラン
    mfa_status = models.IntegerField(default=Statusable.Status.DISABLE.value)  # 2段階認証ステータス（有効無効）
    status = models.IntegerField(default=Status.ENABLE.value)  # ステータス（有効無効停止）
    wf_bpo_task_delegated_stamp_status = models.IntegerField(default=WfBpoTaskDelegatedStampStatus.DISABLE.value)  # ワークフロータスクの「ConPass BPO 代理押印」が有効かどうか
    wf_bpo_task_delegated_receipt_status = models.IntegerField(default=WfBpoTaskDelegatedReceiptStatus.DISABLE.value)  # ワークフロータスクの「ConPass BPO 代理受取」が有効かどうか
    start_date = models.DateField(default=None, blank=True, null=True)  # 開始日
    cancel_date = models.DateField(default=None, blank=True, null=True)  # 解約日
    ipaddress_status = models.IntegerField(default=Statusable.Status.DISABLE.value)  # IPアドレス制限ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='account_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='account_updated_by', blank=True,
                                   null=True, default=None)  # 更新者
    idp_settings = models.JSONField(default=None, blank=True, null=True)  # SSO用のIdP設定
    org_id = models.CharField(max_length=6)  # 組織ID
    sso_status = models.IntegerField(default=SsoStatus.DISABLE.value)  # SSOの契約状態
    chatbot_access=models.BooleanField(default=False)


def __str__(self):
    return self.name
