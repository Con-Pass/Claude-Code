from django.db import models
from conpass.models import Account, Contract, User
from conpass.models.constants.statusable import Statusable


class ArticleLibrary(models.Model, Statusable):
    """
    条文ライブラリ
    """
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING)  # 顧客ID
    template = models.ForeignKey(Contract, on_delete=models.DO_NOTHING)  # 契約書（テンプレート）ID
    meta_name = models.CharField(max_length=255)  # メタ情報の名前
    article = models.TextField()  # 条文テキスト
    reason = models.CharField(max_length=255)  # 修正理由
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='article_library_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='article_library_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.meta_name
