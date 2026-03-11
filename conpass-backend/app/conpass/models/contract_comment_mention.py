from django.db import models
from conpass.models import User, Group, ContractComment
from conpass.models.constants.statusable import Statusable


class ContractCommentMention(models.Model, Statusable):
    """
    メンションされたユーザーの情報を記録
    """
    comment = models.ForeignKey(ContractComment, on_delete=models.DO_NOTHING, related_name='comment_mention')  # コメントID
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='comment_mention_user', blank=True, null=True, default=None)  # 対象ユーザID
    is_read = models.BooleanField(default=False)
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='comment_mention_created_by', blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='comment_mention_updated_by', blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.comment
