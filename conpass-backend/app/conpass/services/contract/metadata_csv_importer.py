import csv
import io
import re
from django.db import transaction
from django.db.models import Q
from conpass.models import MetaData, MetaKey, Contract, DirectoryPermission, Group, User
from conpass.models.constants import Statusable
from conpass.services.contract.contract_enum import AIAgentNotifyEnum
from conpass.services.contract.tasks import  notify_to_AI_agent

from datetime import date


class MetaDataCsvImporter:
    """
    MetaData CSVインポートクラス
    必須項目はIDのみ
    Name以降の項目をMetaKeyとして処理
    """

    DATE_HEADERS = ["契約日", "契約開始日", "契約終了日", "解約ノーティス日(日付)", "関連契約日"]
    SAVE_DATE_HEADERS = ["契約日", "契約開始日", "契約終了日", "関連契約日"]
    DATE_PATTERN_SLASH = re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$")  # yyyy/m/dまたはyyyy/mm/dd形式
    DATE_PATTERN_HYPHEN = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")  # yyyy-m-dまたはyyyy-mm-dd形式

    def __init__(self, contents: str, operated_by):
        self._contents = contents
        self._operated_by = operated_by
        self.errors = []
        self.meta_keys = []

    def _preload_data(self, rows):
        """
        一括で必要なデータをプリロード
        """
        self.all_meta_keys = {mk.name: mk for mk in MetaKey.objects.filter(
            Q(account_id=self._operated_by.account.id) | Q(account_id=None),
            status=Statusable.Status.ENABLE.value,
        )}

        self.all_users = {user.username: user.id for user in User.objects.filter(
            account_id=self._operated_by.account.id,
            status=Statusable.Status.ENABLE.value,
        )}
        self.all_groups = {group.name: group for group in Group.objects.filter(
            account_id=self._operated_by.account.id,
            status=Statusable.Status.ENABLE.value,
        )}

        self.all_contracts = {
            contract.id: contract for contract in Contract.objects.filter(
                id__in={row["ID"] for row in rows if "ID" in row},
                account_id=self._operated_by.account.id
            ).exclude(status=Statusable.Status.DISABLE.value)
        }

        self.directory_permissions = {
            dp.directory_id: dp for dp in DirectoryPermission.objects.filter(
                directory_id__in={contract.directory_id for contract in self.all_contracts.values()},
                status=Statusable.Status.ENABLE.value,
                is_visible=True,
            ).filter(
                Q(user_id=self._operated_by.id) | Q(group_id__in=self.all_groups.values())
            )
        }

    def is_valid(self):
        """
        CSVデータの検証
        """
        reader = csv.DictReader(io.StringIO(self._contents))
        headers = reader.fieldnames

        if not headers:
            self.errors.append({'num': 1, 'message': "CSVヘッダーが存在しません"})
            return False

        headers = [header for header in headers if header.strip()]

        if not set(["ID"]).issubset(headers):
            self.errors.append({'num': 1, 'message': "必須項目（ID）が不足しています"})
            return False

        duplicate_headers = [header for header in headers if headers.count(header) > 1]
        if duplicate_headers:
            self.errors.append({'num': 1, 'message': f"CSVヘッダーに重複があります: {', '.join(duplicate_headers)}"})
            return False

        rows = list(reader)
        self._preload_data(rows)

        for index, row in enumerate(rows, start=2):
            if not row.get("ID"):
                self.errors.append({'num': index, 'field': 'ID', 'message': "IDは必須です"})
                continue

            # 契約存在確認
            try:
                contract_id = int(row["ID"])  # IDを整数型に変換
                contract = self.all_contracts.get(contract_id)
            except ValueError:
                contract = None

            if not contract:
                self.errors.append({'num': index, 'field': 'ID', 'message': f"契約書が存在しません: {row['ID']}"})
                continue

            # ディレクトリ権限確認
            if contract.directory_id not in self.directory_permissions:
                self.errors.append({'num': index, 'field': 'ID', 'message': f"ディレクトリに対する権限がありません: {contract.id}"})

            # 日付検証
            for date_field in self.DATE_HEADERS:
                if date_field in row and row[date_field]:
                    date_value = row[date_field]
                    if self.DATE_PATTERN_SLASH.match(date_value):
                        date_value = date_value.replace("/", "-")
                    elif not self.DATE_PATTERN_HYPHEN.match(date_value):
                        self.errors.append({'num': index, 'field': date_field, 'message': f"{date_field}の形式が不正です: {date_value}"})
                        continue
                    try:
                        year, month, day = map(int, date_value.split("-"))
                        date(year, month, day)
                    except ValueError:
                        self.errors.append({'num': index, 'field': date_field, 'message': f"{date_field}が無効な日付です: {date_value}"})

            # 担当者ユーザーとグループの存在確認
            if "担当者ユーザー" in row and row["担当者ユーザー"]:
                for user_name in row["担当者ユーザー"].split("|"):
                    if user_name.strip() not in self.all_users:
                        self.errors.append({'num': index, 'field': '担当者ユーザー', 'message': f"担当者ユーザーが存在しません: {user_name.strip()}"})

            if "担当者グループ" in row and row["担当者グループ"]:
                for group_name in row["担当者グループ"].split("|"):
                    if group_name.strip() not in self.all_groups:
                        self.errors.append({'num': index, 'field': '担当者グループ', 'message': f"担当者グループが存在しません: {group_name.strip()}"})

        return len(self.errors) == 0

    @transaction.atomic
    def import_metadata(self):
        """
        メタデータをインポート
        """
        if not self.is_valid():
            return False

        reader = csv.DictReader(io.StringIO(self._contents))
        rows = list(reader)
        bulk_metadata_create = []
        bulk_metadata_update = []
        contract_notify_ids=[]

        # 事前に全てのMetaDataを取得して辞書化
        all_meta_data = MetaData.objects.filter(
            contract__in=self.all_contracts.values(),
            key__in=self.all_meta_keys.values()
        ).exclude(status=Statusable.Status.DISABLE.value)

        meta_data_by_contract_and_key = {}
        for meta_data in all_meta_data:
            meta_data_by_contract_and_key.setdefault((meta_data.contract_id, meta_data.key_id), []).append(meta_data)

        # 事前に「担当者名」のMetaDataを取得
        assigned_meta_data_by_contract = MetaData.objects.filter(
            contract__in=self.all_contracts.values(),
            key=self.all_meta_keys.get("担当者名"),
            status=Statusable.Status.ENABLE.value
        ).values_list('contract_id', 'value')

        assigned_users_by_contract = {}
        for contract_id, user_id in assigned_meta_data_by_contract:
            assigned_users_by_contract.setdefault(contract_id, set()).add(user_id)

        for row in rows:
            if not row.get("ID"):
                continue

            contract_id = int(row["ID"])
            contract_notify_ids.append(contract_id)
            contract = self.all_contracts.get(contract_id)
            if not contract:
                continue

            for meta_key_name, meta_key in self.all_meta_keys.items():
                if meta_key_name not in row or meta_key_name in ["担当者ユーザー", "担当者グループ", "担当者名", "解約ノーティス日(日付)"]:
                    continue

                date_value = None
                if meta_key_name in self.SAVE_DATE_HEADERS:
                    date_raw_value = row.get(meta_key_name)
                    if date_raw_value and self.DATE_PATTERN_SLASH.match(date_raw_value):
                        date_value = date_raw_value.replace('/', '-')
                    elif date_raw_value and self.DATE_PATTERN_HYPHEN.match(date_raw_value):
                        date_value = date_raw_value

                existing_meta_data = meta_data_by_contract_and_key.get((contract_id, meta_key.id), [])
                meta_data = existing_meta_data[0] if existing_meta_data else None

                if meta_data:
                    meta_data.value = row[meta_key_name]
                    meta_data.date_value = date_value
                    meta_data.updated_by = self._operated_by
                    bulk_metadata_update.append(meta_data)
                else:
                    bulk_metadata_create.append(MetaData(
                        contract=contract,
                        key=meta_key,
                        value=row[meta_key_name],
                        date_value=date_value,
                        created_by=self._operated_by,
                        updated_by=self._operated_by,
                    ))

            # 「解約ノーティス日(日付)」の処理
            if "解約ノーティス日(日付)" in row and row["解約ノーティス日(日付)"]:
                cancel_notice_date_value = row["解約ノーティス日(日付)"]
                if self.DATE_PATTERN_SLASH.match(cancel_notice_date_value):
                    cancel_notice_date_value = cancel_notice_date_value.replace("/", "-")

                cancel_notice_meta_key = self.all_meta_keys.get("解約ノーティス日")
                if cancel_notice_meta_key:
                    existing_meta_data = meta_data_by_contract_and_key.get((contract_id, cancel_notice_meta_key.id), [])
                    meta_data = existing_meta_data[0] if existing_meta_data else None

                    if meta_data:
                        meta_data.date_value = cancel_notice_date_value
                        meta_data.updated_by = self._operated_by
                        bulk_metadata_update.append(meta_data)
                    else:
                        bulk_metadata_create.append(MetaData(
                            contract=contract,
                            key=cancel_notice_meta_key,
                            date_value=cancel_notice_date_value,
                            created_by=self._operated_by,
                            updated_by=self._operated_by,
                        ))

            # 担当者関連の処理
            if "担当者ユーザー" in row or "担当者グループ" in row:
                assigned_user_ids = []
                if "担当者ユーザー" in row and row["担当者ユーザー"]:
                    assigned_user_ids.extend([self.all_users[name.strip()] for name in row["担当者ユーザー"].split("|") if name.strip() in self.all_users])

                if "担当者グループ" in row and row["担当者グループ"]:
                    for group_name in row["担当者グループ"].split("|"):
                        group = self.all_groups.get(group_name.strip())
                        if group:
                            group_user_ids = group.user_group.filter(
                                status=Statusable.Status.ENABLE.value
                            ).values_list('id', flat=True)
                            assigned_user_ids.extend(group_user_ids)

                assigned_user_ids = list(set(assigned_user_ids))
                current_assigned_users = assigned_users_by_contract.get(contract_id, set())

                users_to_add = set(map(str, assigned_user_ids)) - current_assigned_users
                users_to_remove = current_assigned_users - set(map(str, assigned_user_ids))

                MetaData.objects.filter(
                    contract=contract,
                    key=self.all_meta_keys.get("担当者名"),
                    value__in=users_to_remove,
                    status=Statusable.Status.ENABLE.value
                ).delete()

                for user_id in users_to_add:
                    bulk_metadata_create.append(MetaData(
                        contract=contract,
                        key=self.all_meta_keys.get("担当者名"),
                        value=user_id,
                        created_by=self._operated_by,
                        updated_by=self._operated_by,
                    ))

        if bulk_metadata_update:
            MetaData.objects.bulk_update(bulk_metadata_update, ['value', 'date_value', 'updated_by'])
        if bulk_metadata_create:
            MetaData.objects.bulk_create(bulk_metadata_create)
        notify_to_AI_agent.delay(contract_notify_ids, AIAgentNotifyEnum.UPDATED.value)

        return True
