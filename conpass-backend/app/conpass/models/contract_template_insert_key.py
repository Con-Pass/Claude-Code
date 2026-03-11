from enum import unique, Enum
from django.db import models
from conpass.models import Contract, User
from conpass.models.constants.statusable import Statusable


class ContractTemplateInsertKey(models.Model, Statusable):
    """
    契約書テンプレートに埋め込むことの出来る置換文字列
    companya,companybなどになると思われます
    利用者が自由に設定できるものもある
    """

    @unique
    class Type(Enum):
        FIXED = 1  # 固定：companya などNaturalLanguageで取得できるもの
        FREE = 2

    template = models.ForeignKey(Contract, on_delete=models.DO_NOTHING,
                                 related_name='contract_template_insert_key_template',
                                 blank=True, null=True, default=None)  # 元にした契約書のテンプレートID（ない場合もある）
    name = models.CharField(max_length=255)  # 項目名（便宜上のもの）
    replace_word = models.CharField(max_length=255)  # 置換されるワード（companya などテンプレートに埋め込まれているもの）
    type = models.IntegerField(default=Type.FREE.value)  # 種別（固定、自由）
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='contract_template_insert_key_created_by', blank=True, null=True,
                                   default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='contract_template_insert_key_updated_by', blank=True, null=True,
                                   default=None)  # 更新者

    def __str__(self):
        return self.name
