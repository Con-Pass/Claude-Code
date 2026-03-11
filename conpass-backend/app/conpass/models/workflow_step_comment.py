from django.db import models
from conpass.models import User, WorkflowStep
from conpass.models.constants.statusable import Statusable


class WorkflowStepComment(models.Model, Statusable):
    """
    ワークフローの各ステップに付けられるコメント
    """
    step = models.ForeignKey(WorkflowStep, on_delete=models.DO_NOTHING,
                             related_name='workflow_step_comment_step', blank=True, null=True,
                             default=None)  # ワークフローのステップID
    comment = models.CharField(max_length=255)  # コメント
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                             related_name='workflow_step_comment_user', blank=True, null=True,
                             default=None)  # コメントをしたユーザID
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='workflow_step_comment_created_by', blank=True, null=True,
                                   default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='workflow_step_comment_updated_by', blank=True, null=True,
                                   default=None)  # 更新者

    def __str__(self):
        return self.comment
