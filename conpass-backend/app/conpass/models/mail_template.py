from enum import Enum, unique
from django.db import models
from conpass.models import Account, User
from conpass.models.constants.statusable import Statusable


class MailTemplate(models.Model, Statusable):
    """
    メールテンプレート
    """

    @unique
    class Type(Enum):
        WORKFLOW_CHECK_REQUEST = 1  # ワークフロー確認依頼（adobesignに連携する前）
        CONTRACT_SIGN_CHECK_REQUEST = 2  # 契約書締結確認依頼（adobesignに連携するとき）
        CONTRACT_EXPIRED_INSTANTLY = 3  # 契約書更新依頼：有効期限切れ間近
        CONTRACT_EXPIRED_ALREADY = 4  # 契約書更新依頼：有効期限切れ
        ACCOUNT_CREATED = 5  # アカウント登録完了
        MAIL_HEADER = 6  # メールヘッダ設定
        MAIL_FOOTER = 7  # メールフッタ設定

    template_type = models.CharField(max_length=255, default=Type.WORKFLOW_CHECK_REQUEST.value)  # 種別
    template_text = models.TextField()  # 本文
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING,
                                related_name='mail_template_account',
                                blank=True, null=True, default=None)  # 顧客（アカウント）ID
    is_nest_available = models.BooleanField(default=False)  # 他のテンプレート内で使用可否
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='mail_template_created_by', blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='mail_template_updated_by', blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return str(self.template_type)
