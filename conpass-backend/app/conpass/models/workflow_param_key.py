from enum import Enum, unique
from django.db import models
from conpass.models import User, ContractTemplateInsertKey
from conpass.models.constants.statusable import Statusable


class WorkflowParamKey(models.Model, Statusable):
    """
    ワークフローで使用するメタ情報の項目
    契約書にも反映する場合と、メール宛先などに使うための場合がある
    契約書にも反映する項目の場合、 contract_template_insert_key と紐付けが行われる
    基本的には固定
    """

    @unique
    class Type(Enum):
        STRING = 1  # 文字
        INTEGER = 2  # 数値

    name = models.CharField(max_length=255)  # 項目名
    type = models.IntegerField(default=Type.STRING.value)  # 種別（string/integerなど）
    contract_template_insert_key = models.ForeignKey(ContractTemplateInsertKey,
                                                     on_delete=models.DO_NOTHING,
                                                     related_name='workflow_param_key_contract_template_insert_key',
                                                     blank=True, null=True, default=None)  # 契約書のテンプレートに反映出来る場合はその項目ID
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='workflow_param_key_created_by', blank=True, null=True,
                                   default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='workflow_param_key_updated_by', blank=True, null=True,
                                   default=None)  # 更新者

    def __str__(self):
        return self.name
