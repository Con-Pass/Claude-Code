from django.db import models
from conpass.models import User, Contract, MetaKey
from conpass.models.constants.statusable import Statusable


class MetaData(models.Model, Statusable):
    """
    NaturalLanguageで解析したメタ情報
    ユーザが自由に作る項目もある
    """
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING,
                                 related_name='meta_data_contract', blank=True, null=True, default=None)  # 契約書ID
    key = models.ForeignKey(MetaKey, on_delete=models.DO_NOTHING, related_name='meta_data_key',
                            blank=True, null=True, default=None)  # メタ情報項目ID
    check = models.BooleanField(default=False)  # ユーザによる確認をしたかどうか
    checked_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='meta_data_checked_by', blank=True,
                                   null=True, default=None)  # チェックを入れたユーザ
    value = models.CharField(max_length=255, blank=True, default='')  # 値
    date_value = models.DateField(null=True, default=None)  # 日付項目値
    choice_key = models.IntegerField(blank=True,null=True)
    choice_selector= models.CharField(max_length=255, null=True)
    choice_value = models.CharField(max_length=255, null=True)
    score = models.FloatField(default=0.0)  # NLで解析した時のスコア（0.0～1.0、高いほど良い）
    start_offset = models.IntegerField(default=0)  # NLで解析した時のテキスト全体での抽出開始位置
    end_offset = models.IntegerField(default=0)  # NLで解析した時のテキスト全体での抽出終了位置
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    lock = models.BooleanField(default=False)  # 編集可否
    created_at = models.DateTimeField(auto_now_add=True)  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='meta_data_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField(auto_now=True)  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='meta_data_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.contract.name + " " + self.key.name
