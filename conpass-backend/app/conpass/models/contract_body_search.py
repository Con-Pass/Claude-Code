from django.db import models
from conpass.models import ContractBody, User
from conpass.models.constants.statusable import Statusable


class ContractBodySearch(models.Model, Statusable):
    """
    契約書の本文を検索するためのモデル
    """
    contract_body = models.ForeignKey(ContractBody, on_delete=models.CASCADE,
                                      related_name='contract_body_searches')
    search_body = models.TextField()  # 日本語で保存された本文
    created_at = models.DateTimeField(auto_now_add=True)  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='contract_body_search_created_by',
                                   blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField(auto_now_add=True)  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='contract_body_search_updated_by',
                                   blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.contract.name + ' ' + self.updated_at.__str__()
