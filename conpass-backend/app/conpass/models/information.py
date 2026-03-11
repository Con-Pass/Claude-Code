from django.db import models
from conpass.models import User
from conpass.models.constants.statusable import Statusable


class Information(models.Model, Statusable):
    """
    お知らせ
    基本的に管理者（パープル様）が作成、管理します
    特定の顧客に対しての告知などは考慮しない
    """
    title = models.CharField(max_length=255)  # 記事タイトル
    body = models.TextField()  # 記事本文
    url = models.CharField(max_length=255)  # 参考URL
    order = models.IntegerField(default=0)  # 表示優先順位（数字大：上位）
    start_at = models.DateTimeField()  # 配信開始日時
    end_at = models.DateTimeField()  # 配信終了日時
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='information_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='information_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.title
