from django.db import models
from conpass.models import User, Group, WorkflowTask
from conpass.models.constants.statusable import Statusable


class WorkflowTaskUser(models.Model, Statusable):
    """
    ワークフローのタスクと担当者の紐づけ
    タスクに対しては、ユーザ（担当者）が１人以上、もしくはグループが１組以上紐づく
    タスクを完了したかどうかはここで指定します。
    グループの場合はグループ内の誰か１人が完了でグループ単位としては完了とします
    """
    task = models.ForeignKey(WorkflowTask, on_delete=models.DO_NOTHING,
                             related_name='workflow_task_user_task')  # ワークフローのタスクID
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, blank=True, null=True, default=None)
    group = models.ForeignKey(Group, on_delete=models.DO_NOTHING, blank=True, null=True, default=None)
    is_finish = models.BooleanField(default=False)  # その担当者がタスクを完了したかどうか
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='workflow_task_user_created_by', blank=True, null=True,
                                   default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='workflow_task_user_updated_by', blank=True, null=True,
                                   default=None)  # 更新者

    def __str__(self):
        return self.task.__str__() + " " + self.user.__str__()
