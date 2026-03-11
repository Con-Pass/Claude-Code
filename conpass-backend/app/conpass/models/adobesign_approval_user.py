from django.db import models

from conpass.models import AdobeSign, User
from conpass.models.constants.statusable import Statusable


class AdobeSignApprovalUser(models.Model, Statusable):
    """
    AdobeSign連携情報
    """
    adobesign = models.ForeignKey(AdobeSign, on_delete=models.DO_NOTHING,
                                  related_name='adobesign_approval_user_adobesign', blank=True,
                                  null=True, default=None)  # adobeSignID
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='adobesign_approval_user_user', blank=True,
                             null=True, default=None)  # ユーザーID
    approval_mail_address = models.CharField(max_length=255, blank=True,
                                             null=True, default=None)  # 承認先（委任も含む）メールアドレス
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='adobesign_approval_user_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='adobesign_approval_user_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.adobesign.__str__() + " " + self.user.__str__()
