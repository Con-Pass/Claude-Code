import pytest

from conpass.models import User
from conpass.services.user.user_csv_importer import UserClientCsvRowSerializer, UserClientCsvImporter
from conpass.tests.factories.client import ClientFactory
from conpass.tests.factories.user import UserFactory


@pytest.fixture
def contents():
    return """メールアドレス,名前,部署名,役職,電話番号,備考
user001@example.com,田中太朗,営業部,部長,03-0000-0000,メモ1
user002@example.com,田中次郎,営業部,部長,03-0000-0001,メモ2
""".replace('\n', '\r\n')


@pytest.fixture
def invalid_contents():
    return """メールアドレス,名前,部署名,役職,電話番号,備考
user001@example.com,田中太朗
user002@example.com,田中次郎,営業部,部長,03-0000-0001,メモ2
""".replace('\n', '\r\n')


class TestUserClientCsvImporter:
    @pytest.mark.django_db
    def test__importer__valid(self, contents):
        client = ClientFactory()
        user = UserFactory()
        importer = UserClientCsvImporter(contents=contents, client=client, operated_by=user)
        assert importer.is_valid()

    @pytest.mark.django_db
    def test__importer__valid__登録できること(self, contents):
        client = ClientFactory()
        user = UserFactory()
        importer = UserClientCsvImporter(contents=contents, client=client, operated_by=user)
        importer.is_valid()
        importer.import_users()
        assert User.objects.get(login_name=f"user001@example.com:{client.id}")
        assert User.objects.get(login_name=f"user002@example.com:{client.id}")

    @pytest.mark.django_db
    def test__importer__valid__メールアドレス(self, contents):
        client = ClientFactory()
        user = UserFactory()
        importer = UserClientCsvImporter(contents=contents, client=client, operated_by=user)
        importer.is_valid()
        importer.import_users()
        assert 'user001@example.com' == User.objects.get(login_name=f"user001@example.com:{client.id}").email
        assert 'user002@example.com' == User.objects.get(login_name=f"user002@example.com:{client.id}").email

    @pytest.mark.django_db
    def test__importer__invalid(self, invalid_contents):
        client = ClientFactory()
        user = UserFactory()
        importer = UserClientCsvImporter(contents=invalid_contents, client=client, operated_by=user)
        assert not importer.is_valid()


class TestUserClientCsvRowSerializer:
    @pytest.mark.parametrize('case,login_name,username,division,position,tel,memo,expected', [
        ['OK:正常', 'admin001@example.com', '田中太朗', '営業部', '部長', '03-0000-1111', 'メモメモ', True],
        ['NG:メールアドレスが空欄', '', '田中太朗', '営業部', '部長', '03-0000-1111', 'メモメモ', False],
        ['NG:名前が空欄', 'admin001@example.com', '', '営業部', '部長', '03-0000-1111', 'メモメモ', False],
        ['OK:部署名が空欄', 'admin001@example.com', '田中太朗', '', '部長', '03-0000-1111', 'メモメモ', True],
        ['OK:役職名が空欄', 'admin001@example.com', '田中太朗', '営業部', '', '03-0000-1111', 'メモメモ', True],
        ['OK:電話番号が空欄', 'admin001@example.com', '田中太朗', '営業部', '部長', '', 'メモメモ', True],
        ['OK:メモが空欄', 'admin001@example.com', '田中太朗', '営業部', '部長', '03-0000-1111', '', True],
    ])
    def test__serializer__blank(self, case, login_name, username, division, position, tel, memo, expected):
        serializer = UserClientCsvRowSerializer(data={
            "login_name": login_name,
            "username": username,
            "division": division,
            "position": position,
            "tel": tel,
            "memo": memo,
        })

        assert serializer.is_valid() == expected
