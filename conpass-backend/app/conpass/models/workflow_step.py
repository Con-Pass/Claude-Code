from django.db import models
from conpass.models import User, Workflow
from conpass.models.constants.statusable import Statusable


class WorkflowStep(models.Model, Statusable):
    """
    ワークフローのステップ
    ステップが次に進む条件は、紐づくタスクがすべて完了になること
    """
    name = models.CharField(max_length=255)  # 本ステップの名称（任意）
    workflow = models.ForeignKey(Workflow, on_delete=models.DO_NOTHING)  # ワークフローID
    parent_step = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='workflow_step_parent',
                                    blank=True, null=True, default=None)  # 親ステップID blankは始点
    child_step = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='workflow_step_child',
                                   blank=True, null=True, default=None)  # 子ステップID blankは終点
    memo = models.CharField(max_length=255)  # 備考
    reject_step_count = models.IntegerField(default=1)  # リジェクトされた時何ステップ分前まで戻るか
    start_date = models.DateTimeField(blank=True, null=True, default=None)  # 本ステップが開始された日時
    end_date = models.DateTimeField(blank=True, null=True, default=None)  # 本ステップが完了した日時
    expire_day = models.IntegerField()  # 本ステップが開始されてからの期限（日数）
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='workflow_step_created_by',
                                   blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='workflow_step_updated_by',
                                   blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.name
