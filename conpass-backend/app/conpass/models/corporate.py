from django.db import models
from conpass.models import Account
from conpass.models.constants.statusable import Statusable


class Corporate(models.Model, Statusable):
    """
    法人
    ConPass利用者、連絡先（取引先）いずれからも使用されます
    """
    name = models.CharField(max_length=255)  # 会社名
    address = models.CharField(max_length=255)  # 住所
    executive_name = models.CharField(max_length=255)  # 代表者名
    sales_name = models.CharField(max_length=255)  # 営業担当者名
    service = models.CharField(max_length=255)  # 商品／サービス名
    url = models.CharField(max_length=255)  # サイトURL
    tel = models.CharField(max_length=255)  # 電話番号
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING,
                                related_name='corporate_account', blank=True, null=True,
                                default=None)  # アカウント
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='corporate_created_by', blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='corporate_updated_by', blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.name
