from enum import Enum, unique
from django.db import models
from conpass.models import User, WorkflowStep, WorkflowTaskMaster
from conpass.models.constants.statusable import Statusable


class WorkflowTask(models.Model, Statusable):
    """
    ワークフローのタスク
    ステップに対し、タスクは１つ以上紐付けられる
    タスクに対しては、ユーザ（担当者）が１人以上紐づく
    複数人が担当の場合、このタスクを完了にする条件は finish_condition で定義されます
    担当は最低１人必要
    タスクの内容についてはマスタで別に管理する
    """

    @unique
    class FinishCondition(Enum):
        ONE = 1  # だれか一人が完了
        ALL = 2  # 全員が完了

    @unique
    class AuthorNotifyCondition(Enum):
        TRUE = 1  # 送信する
        FALSE = 2  # 送信しない

    name = models.CharField(max_length=255, default="")  # 名前
    step = models.ForeignKey(WorkflowStep, on_delete=models.DO_NOTHING,
                             related_name='workflow_task_step', blank=True, null=True, default=None)  # ワークフローのステップID
    task = models.ForeignKey(WorkflowTaskMaster, on_delete=models.DO_NOTHING,
                             related_name='workflow_task_task', blank=True, null=True, default=None)  # ワークフローのタスクマスタID
    is_finish = models.BooleanField(default=False)  # タスクが完了しているかどうか
    finish_condition = models.IntegerField(default=FinishCondition.ALL.value)  # タスクの完了条件（紐づく全員が完了、or一人が完了）
    author_notify = models.IntegerField(default=AuthorNotifyCondition.FALSE.value)  # タスクの完了メールを申請者に送信するかどうか
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='workflow_task_created_by', blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='workflow_task_updated_by', blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.name
