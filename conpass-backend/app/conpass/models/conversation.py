from django.db import models
from conpass.models import Contract, User
from conpass.models.constants.statusable import Statusable


class Conversation(models.Model, Statusable):
    """
    契約書のコメント
    """

    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, related_name='conversation_contract')  # 契約書ID
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='conversation_user', blank=True, null=True,
                             default=None)  # ユーザID
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField(auto_now_add=True)  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING, related_name='conversation_created_by',
                                   blank=True, null=True, default=None)  # 登録者（userと重複？）
    updated_at = models.DateTimeField(auto_now=True)  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING, related_name='conversation_updated_by',
                                   blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.contract.name
