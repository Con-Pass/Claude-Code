from django.db import models
from conpass.models import Conversation, Contract, User
from conpass.models.constants.statusable import Statusable


class ConversationComment(models.Model, Statusable):
    """
    契約書のコメントの返信
    """
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, related_name='conversation_comment_contract')  # 契約書ID
    conversation = models.ForeignKey(Conversation, on_delete=models.DO_NOTHING,
                                     related_name='conversation_comment_conversation')  # コメントID
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='conversation_comment_user', blank=True,
                             null=True, default=None)  # ユーザID
    author = models.CharField(max_length=255, null=True, default=None)  # コメント者
    comment = models.TextField()  # コメント本文
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField(auto_now_add=True)  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING, related_name='conversation_comment_created_by',
                                   blank=True, null=True, default=None)  # 登録者（userと重複？）
    updated_at = models.DateTimeField(auto_now=True)  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING, related_name='conversation_comment_updated_by',
                                   blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.comment
