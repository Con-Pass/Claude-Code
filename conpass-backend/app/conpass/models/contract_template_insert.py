from django.db import models
from conpass.models import Contract, ContractTemplateInsertKey, User
from conpass.models.constants.statusable import Statusable


class ContractTemplateInsert(models.Model, Statusable):
    """
    契約書テンプレートにどのようなメタ情報の種別（Entity）が埋め込まれているか
    たとえば、companya、companyb が設定されている場合、それがメタ情報の企業名甲、乙でそれぞれ置換される
    """
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING,
                                 related_name='contract_template_insert_contract',
                                 blank=True, null=True, default=None)  # 契約書ID
    meta_key = models.ForeignKey(ContractTemplateInsertKey, on_delete=models.DO_NOTHING,
                                 related_name='contract_template_insert_meta_key',
                                 blank=True, null=True, default=None)  # 挿入できる項目ID
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='contract_template_insert_created_by', blank=True, null=True,
                                   default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='contract_template_insert_updated_by', blank=True, null=True,
                                   default=None)  # 更新者

    def __str__(self):
        return self.contract.name + " " + self.meta_key.name
