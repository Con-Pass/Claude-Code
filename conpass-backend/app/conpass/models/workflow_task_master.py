from enum import Enum, unique
from django.db import models
from conpass.models import User
from conpass.models.constants.statusable import Statusable


class WorkflowTaskMaster(models.Model, Statusable):
    """
    ワークフローのタスクのマスタ
    変更不可のデフォルトのものと、ユーザが任意に設定できるものがある
    """

    class Type(Enum):
        """
        ワークフロータスクの種別は表示するアイコンや必要なパラメータの判定などに使用します
        """
        COMMON = 0  # いずれも当てはまらない汎用的な作業
        APPROVE = 1  # 承認
        DOCUMENT = 2  # 文章作成
        AGREEMENT = 3  # 合意
        SIGN = 4  # （外部サービスを使って）電子署名（メール）
        OUTSIDE = 5  # システム外の作業
        DOWNLOAD = 6  # ダウンロード
        UPLOAD = 7  # アップロード
        EMAIL = 8  # Eメール（郵送ではない）
        MAIL = 9  # なにか物理的な郵送
        DELIVERLY = 10  # なにか物理的な配送
        BPO_ADMIN_APPROVE = 11  # [BPO契約管理者]承認
        BPO_BOOKBUILDING_STAMP_MAIL = 12  # [BPO]印刷製本・押印・郵送
        BPO_RECEIPT = 13  # [BPO]受取
        BPO_SCANNING_UPLOAD = 14  # [BPO]スキャニング・アップロード
        BPO_STORAGE_RETURN = 15  # [BPO]原本の保管または返却
        SIGN_URL = 16  # （外部サービスを使って）電子署名（URL）

    name = models.CharField(max_length=255)  # 名前
    description = models.CharField(max_length=255)  # タスクの内容
    type = models.IntegerField(default=Type.COMMON.value)  # タスクの種別（承認、送信、郵送、印刷など）
    is_need_contract = models.BooleanField()  # タスクに契約書（contractIdのあるもの）が必要かどうか
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='workflow_task_master_created_by', blank=True, null=True,
                                   default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='workflow_task_master_updated_by', blank=True, null=True,
                                   default=None)  # 更新者

    def __str__(self):
        return self.name
