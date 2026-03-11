import pytest

from conpass.models import Client
from conpass.services.client.client_csv_importer import ClientCsvImporter, ClientCsvRowSerializer
from conpass.tests.factories.user import UserFactory


@pytest.fixture
def contents():
    return """会社名,住所,代表者名,営業担当者名 （担当グループ名）
株式会社〇〇,東京都〇〇,代表太朗,営業太朗
株式会社△△,東京都△△,代表次朗,営業次朗
""".replace('\n', '\r\n')


@pytest.fixture
def invalid_contents():
    return """会社名,住所,代表者名,営業担当者名 （担当グループ名）
株式会社〇〇,,代表太朗,営業太朗
株式会社△△,東京都△△,代表次朗,営業次朗
""".replace('\n', '\r\n')


class TestClientCsvImporter:
    @pytest.mark.django_db
    def test__importer__valid(self, contents):
        user = UserFactory()
        importer = ClientCsvImporter(contents=contents, operated_by=user)
        assert importer.is_valid()

    @pytest.mark.django_db
    def test__importer__valid__登録できること(self, contents):
        user = UserFactory()
        importer = ClientCsvImporter(contents=contents, operated_by=user)
        assert importer.is_valid()
        importer.import_clients()
        assert Client.objects.get(name='株式会社〇〇')
        assert Client.objects.get(name='株式会社△△')

    @pytest.mark.django_db
    def test__importer__valid__各項目(self, contents):
        user = UserFactory()
        importer = ClientCsvImporter(contents=contents, operated_by=user)
        assert importer.is_valid()
        importer.import_clients()
        client1 = Client.objects.get(name='株式会社〇〇')
        client2 = Client.objects.get(name='株式会社△△')
        assert '株式会社〇〇' == client1.name
        assert '株式会社〇〇' == client1.corporate.name
        assert '東京都〇〇' == client1.corporate.address
        assert '代表太朗' == client1.corporate.executive_name
        assert '営業太朗' == client1.corporate.sales_name
        assert user.account == client1.provider_account

        assert '株式会社△△' == client2.name
        assert '株式会社△△' == client2.corporate.name
        assert '東京都△△' == client2.corporate.address
        assert '代表次朗' == client2.corporate.executive_name
        assert '営業次朗' == client2.corporate.sales_name
        assert user.account == client2.provider_account

    @pytest.mark.django_db
    def test__importer__invalid__バリデーションエラーがひとつでもあれば登録しない(self, invalid_contents):
        user = UserFactory()
        importer = ClientCsvImporter(contents=invalid_contents, operated_by=user)
        assert not importer.is_valid()
        assert not Client.objects.filter(name='株式会社〇〇').exists()
        assert not Client.objects.filter(name='株式会社△△').exists()


class TestUserClientCsvRowSerializer:
    @pytest.fixture
    def data(self):
        return {
            "name": '会社名テスト',
            "address": '住所テスト',
            "executive_name": '代表者名テスト',
            "sales_name": '営業担当者名 （担当グループ名）テスト',
        }

    def test__serializer(self, data):
        serializer = ClientCsvRowSerializer(data=data)

        assert serializer.is_valid(), serializer.errors

    @pytest.mark.parametrize('case,key,value,is_valid', [
        ['会社名_必須', 'name', '', False],
        ['住所_必須', 'address', '', False],
        ['代表者名_必須', 'executive_name', '', False],
        ['営業担当者名 （担当グループ名）_必須', 'sales_name', '', False],
        ['会社名_最大文字列255', 'name', 'a' * 255, True],
        ['住所_最大文字列255', 'address', 'a' * 255, True],
        ['代表者名_最大文字列255', 'executive_name', 'a' * 255, True],
        ['営業担当者名 （担当グループ名）_最大文字列255', 'sales_name', 'a' * 255, True],
        ['会社名_最大文字列256', 'name', 'a' * 256, False],
        ['住所_最大文字列256', 'address', 'a' * 256, False],
        ['代表者名_最大文字列256', 'executive_name', 'a' * 256, False],
        ['営業担当者名 （担当グループ名）_最大文字列256', 'sales_name', 'a' * 256, False],
    ])
    def test_serializer_validation(self, data, case, key, value, is_valid):
        data[key] = value
        serializer = ClientCsvRowSerializer(data=data)

        assert is_valid == serializer.is_valid(), case
