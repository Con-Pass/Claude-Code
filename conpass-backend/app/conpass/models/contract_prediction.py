from django.db import models
from conpass.models import User, Contract, File, ContractBody
from conpass.models.constants.statusable import Statusable


class ContractPrediction(models.Model, Statusable):
    """
    契約書をNaturalLanguageで解析した結果
    ファイルが無い状態で先に登録されたcontract_body を対象にする場合もある
    """
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING)  # 契約書ID
    contract_body = models.ForeignKey(ContractBody, on_delete=models.DO_NOTHING, blank=True, null=True,
                                      default=None)  # 解析対象にした本文ID
    file = models.ForeignKey(File, on_delete=models.DO_NOTHING, blank=True, null=True, default=None)  # 解析対象にしたファイルID
    entity = models.CharField(max_length=255)  # ラベル
    score = models.FloatField()  # 評価値（max1.0）
    content = models.CharField(max_length=255)  # 取得した値。VisionAIで画像からOCRしているため誤字が割とある
    start = models.IntegerField()  # 取得範囲開始
    end = models.IntegerField()  # 取得範囲終了
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='contract_prediction_created_by', blank=True, null=True,
                                   default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='contract_prediction_updated_by', blank=True, null=True,
                                   default=None)  # 更新者

    def __str__(self):
        return self.contract.name + " " + self.entity
