from django.db import models
from conpass.models import WorkflowParamKey, User
from conpass.models.constants.statusable import Statusable


class WorkflowParam(models.Model, Statusable):
    """
    ワークフローで使う情報
    契約書に埋め込むメタ情報や、メール送信などにつかう宛先、メールアドレスなど
    key名は WorkflowParamKey で管理
    """
    key = models.ForeignKey(WorkflowParamKey, on_delete=models.DO_NOTHING,
                            related_name='workflow_param_key', blank=True, null=True, default=None)  # 関連情報の項目ID
    value = models.CharField(max_length=255)  # 値。取引先の名前など
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='workflow_param_created_by',
                                   blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='workflow_param_updated_by',
                                   blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.key.name
