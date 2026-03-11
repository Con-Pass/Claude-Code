from enum import Enum, unique
from django.db import models

from conpass.models.constants.statusable import Statusable


class MailTag(models.Model, Statusable):
    """
    メールテンプレートのタグ
    """
    @unique
    class MailTagConst(Enum):
        HEADER = '{header}'  # {header}
        FOOTER = '{footer}'  # {footer}
        CLIENT = '{contract:client}'  # {contract:client}
        CONCLUDE_DATE = '{contract:concludeDate}'  # {contract:concludeDate}
        LIMIT_DATE = '{contract:limitDate}'  # {contract:limitDate}
        DETAIL_URL = '{contract:detailUrl}'  # {contract:detailUrl}
        RENEW_URL = '{contract:renewUrl}'  # {contract:renewUrl}

    tag = models.CharField(max_length=255)  # タグ
    text = models.CharField(max_length=255)  # 内容
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='mail_tag_created_by', blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='mail_tag_updated_by', blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.tag
