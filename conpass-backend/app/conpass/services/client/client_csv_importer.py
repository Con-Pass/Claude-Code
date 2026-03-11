import csv
import datetime
import io
from logging import getLogger

from django.utils.timezone import make_aware
from rest_framework import serializers

from conpass.models import User, Client, Corporate

logger = getLogger(__name__)


class ClientCsvRowSerializer(serializers.Serializer):
    name = serializers.CharField(required=True, allow_blank=False, max_length=255)
    address = serializers.CharField(required=True, allow_blank=False, max_length=255)
    executive_name = serializers.CharField(required=True, allow_blank=False, max_length=255)
    sales_name = serializers.CharField(required=True, allow_blank=False, max_length=255)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass


class ClientCsvImporter:
    filed_names = [
        "会社名",
        "住所",
        "代表者名",
        "営業担当者名 （担当グループ名）",
    ]

    field_mapping = {
        "会社名": "name",
        "住所": "address",
        "代表者名": "executive_name",
        "営業担当者名 （担当グループ名）": "sales_name",
    }

    field_reverse_mapping = {
        v: k for k, v in field_mapping.items()
    }

    def __init__(self, contents: str, operated_by: User):
        self._contents = contents
        self._operated_by = operated_by
        self._validated = False
        self.errors = []

    def import_clients(self):
        if not self._validated:
            raise self.NotValidatedError

        reader = csv.DictReader(io.StringIO(self._contents))
        for row in reader:
            now = make_aware(datetime.datetime.now())
            corporate = Corporate(
                name=row['会社名'],
                address=row['住所'],
                executive_name=row['代表者名'],
                sales_name=row['営業担当者名 （担当グループ名）'],
                account_id=self._operated_by.account_id,
                created_by=self._operated_by,
                created_at=now,
                updated_by=self._operated_by,
                updated_at=now,
            )
            corporate.save()
            client = Client(
                name=row['会社名'],
                corporate=corporate,
                provider_account_id=self._operated_by.account_id,
                created_by=self._operated_by,
                created_at=now,
                updated_by=self._operated_by,
                updated_at=now,
            )
            client.save()

    def is_valid(self):
        reader = csv.DictReader(io.StringIO(self._contents))
        if reader.fieldnames != self.filed_names:
            self.errors.append({
                'num': 1,
                'name': '',
                'message': "ヘッダ行が不正です",
            })
            return False

        for index, row in enumerate(reader):
            serializer = ClientCsvRowSerializer(data=self._convert_key(row))
            if not serializer.is_valid():
                for key, messages in serializer.errors.items():
                    for message in messages:
                        self.errors.append({
                            'num': index + 2,
                            'name': self.field_reverse_mapping[key],
                            'message': message,
                        })

        self._validated = True
        return len(self.errors) == 0

    def _convert_key(self, row: dict):
        return {
            self.field_mapping[k]: v for k, v in row.items()
        }

    class NotValidatedError(Exception):
        pass

    class UserDuplicateError(Exception):
        pass
