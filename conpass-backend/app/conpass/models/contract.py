from typing import Optional

from django.db import models
from conpass.models import Directory, File, Account
from conpass.models.constants import ContractTypeable, Statusable
from conpass.models.constants.contractstatusable import ContractStatusable
from conpass.models.constants.typeable import Typeable


class Contract(models.Model, ContractStatusable, ContractTypeable):
    """
    契約書
    契約書のテンプレート、実際の契約書、過去契約書（締結済をアップロードされたもの）はすべてここで管理とします
    """

    name = models.CharField(max_length=255)  # 契約書名
    type = models.IntegerField(default=ContractTypeable.ContractType.CONTRACT.value)  # 種別（通常の契約書、テンプレート、過去契約書）
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING, related_name='contract_account',
                                blank=True, null=True, default=None)  # 顧客ID
    client = models.ForeignKey('conpass.Client', on_delete=models.DO_NOTHING, related_name='contract_client',
                               blank=True, null=True, default=None)  # 契約先相手のID
    directory = models.ForeignKey(Directory, on_delete=models.DO_NOTHING, related_name='contract_directory',
                                  blank=True, null=True, default=None)  # 階層ID
    template = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='contract_template',
                                 blank=True, null=True, default=None)  # 元にした契約書のテンプレートID（ない場合もある）
    origin = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='contract_origin',
                               blank=True, null=True, default=None)  # 一番上の親（このデータにはtemplateが無い）
    parent = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='contract_parent',
                               blank=True, null=True, default=None)  # 親（更新する時などに入る）
    version = models.CharField(max_length=255, default="")  # バージョン名
    file = models.ManyToManyField(File, blank=True, related_name='contract_files')  # 実際のファイル情報ID
    is_garbage = models.BooleanField(default=False)  # ゴミ箱に所属
    is_provider = models.BooleanField(default=True)  # 自社のものかどうか
    is_open = models.BooleanField(default=True)  # 公開フラグ
    is_new_lease= models.BooleanField(default=False)
    bulk_zip_path = models.CharField(blank=True, null=True, default=None, max_length=255)  # 一括アップロードのzipファイルパス
    status = models.IntegerField(default=ContractStatusable.Status.ENABLE.value)  # ステータス（有効無効）
    related_contracts = models.ManyToManyField("self", blank=True, symmetrical=False, related_name='contracts_related_to_me')
    lease_key= models.ManyToManyField('conpass.LeaseKey', related_name='contracts')
    is_child_contract= models.BooleanField(null=True)
    related_parent= models.ForeignKey("self", blank=True, null=True, on_delete=models.SET_NULL, related_name="children")
    candidates=models.ManyToManyField("self", blank=True, related_name='related_candidates')
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='contract_created_by', blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='contract_updated_by', blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.name

    def get_files(self, filters=None):
        if filters is None:
            filters = {}
        wheres = {
            'status': File.Status.ENABLE.value,
        }
        if filters:
            wheres.update(filters)
        files = self.file.filter(**wheres)
        return list(files.all())

    def get_bpo_correction_response(self):
        correction_request = self.correction_request_contract.order_by('-updated_at').first()
        return correction_request.response if correction_request else None

    def get_adopted_version(self):
        wheres = {
            'status': Statusable.Status.ENABLE.value,
            'is_adopted': Statusable.Status.ENABLE.value,
        }
        if self.contract_body_contract.filter(**wheres).order_by('-updated_at').first():
            contract_body = self.contract_body_contract.filter(**wheres).order_by('-updated_at').first()
        else:
            return None
        return contract_body.version

    def get_comments(self):
        # 削除されたコメントをフロントで表示するために、status が Statusable.Status.DISABLEも意図的に対象にしてます。
        comments = self.contract_comment_contract.order_by('-linked_version', '-created_at')
        return comments if comments else None

    def get_end_date(self):
        return self._get_meta_date_value('contractenddate')

    def get_notice_date(self):
        return self._get_meta_date_value('cancelnotice')

    def get_title(self):
        return self._get_meta_value('title')

    def get_companies_a(self):
        return self._get_meta_values('companya')

    def get_companies_b(self):
        return self._get_meta_values('companyb')

    def get_companies_c(self):
        return self._get_meta_values('companyc')

    def get_companies_d(self):
        return self._get_meta_values('companyd')

    def get_contract_date(self):
        return self._get_meta_date_value('contractdate')

    def get_auto_update(self):
        return self._get_meta_value('autoupdate')

    def get_contract_start_date(self):
        return self._get_meta_date_value('contractstartdate')

    def get_doc_id(self):
        return self._get_meta_value('docid')

    def get_related_contract_date(self):
        return self._get_meta_date_value('related_contract_date')

    def get_conpass_amount(self):
        return self._get_meta_value('conpass_amount')

    def get_antisocial(self):
        return self._get_meta_value('antisocial')

    def get_related_contract(self):
        return self._get_meta_value('related_contract')

    def get_cort(self):
        return self._get_meta_value('cort')

    def get_conpass_contract_type(self):
        return self._get_meta_value('conpass_contract_type')

    def get_conpass_person(self):
        return self._get_meta_value('conpass_person')

    def _get_meta_date_value(self, key: str):
        if obj := self._get_meta_date_object(key):
            return obj.date_value
        return None

    def _get_meta_value(self, key: str):
        if obj := self._get_meta_object(key):
            return obj.value
        return None

    def _get_meta_date_values(self, key: str):
        if objs := self._get_meta_date_objects(key):
            return list(map(lambda x: x.date_value, objs))
        return []

    def _get_meta_values(self, key: str):
        if objs := self._get_meta_objects(key):
            return list(map(lambda x: x.value, objs))
        return []

    def _get_meta_object(self, key: str):
        for meta_data in self.meta_data_contract.filter(status=Statusable.Status.ENABLE.value).order_by('value').all():
            if meta_data.key.label == key:
                return meta_data
        return None

    def _get_meta_objects(self, key: str):
        ret = []
        for meta_data in self.meta_data_contract.filter(status=Statusable.Status.ENABLE.value).order_by('value').all():
            if meta_data.key.label == key:
                ret.append(meta_data)
        return ret

    def _get_meta_date_object(self, key: str):
        # 一番新しい日付を一つだけ返す
        for meta_data in self.meta_data_contract.filter(status=Statusable.Status.ENABLE.value).order_by('-date_value').all():
            if meta_data.key.label == key:
                return meta_data
        return None

    def _get_meta_date_objects(self, key: str):
        ret = []
        for meta_data in self.meta_data_contract.filter(status=Statusable.Status.ENABLE.value).order_by('date_value').all():
            if meta_data.key.label == key:
                ret.append(meta_data)
        return ret

    def get_free_meta_datas(self):
        ret = []
        if datas := self._get_free_meta_datas():
            for data in datas:
                ret.append({
                    'keyId': data.key.id,
                    'keyName': data.key.name,
                    'value': data.value,
                })
        return ret

    def _get_free_meta_datas(self):
        wheres = {
            'key__type': Typeable.Type.FREE.value,
            'key__account': self.account,
            'key__status': Statusable.Status.ENABLE.value,
            'status': Statusable.Status.ENABLE.value,
        }
        return self.meta_data_contract.filter(**wheres).order_by('key_id').all()
