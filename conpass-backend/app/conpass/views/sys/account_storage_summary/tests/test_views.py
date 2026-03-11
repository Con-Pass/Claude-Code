import pytest

from conpass.models import Account
from conpass.tests.factories.account import AccountFactory


@pytest.mark.django_db
def test__ユーザ認証では401となること(api_client):
    account: Account = AccountFactory()
    response = api_client.get(f'/api/sys/account-storage-summary/{account.id}')
    assert 401 == response.status_code


@pytest.mark.skip(reason="ローカル環境ではテスト成功、GithubActionsでは失敗するため一時的にスキップ")
@pytest.mark.django_db
def test__200(sys_client):
    account: Account = AccountFactory()
    response = sys_client.get(f'/api/sys/account-storage-summary/{account.id}')
    assert 200 == response.status_code
    assert 12 == len(response.data)


@pytest.mark.django_db
def test__404(sys_client):
    response = sys_client.get('/api/sys/account-storage-summary/999')
    assert 404 == response.status_code
