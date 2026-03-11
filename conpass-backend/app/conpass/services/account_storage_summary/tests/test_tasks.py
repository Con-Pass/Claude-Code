import pytest

from conpass.services.account_storage_summary import tasks
from conpass.tests.factories.account import AccountFactory


@pytest.mark.django_db
def test__create_daily_summary():
    AccountFactory.create_batch(3)
    result = tasks.create_daily_account_storage_summary_execute("2020-01-01")
    assert result['succeeded'] == 3


@pytest.mark.django_db
def test__create_monthly_summary():
    AccountFactory.create_batch(3)
    result = tasks.create_monthly_account_storage_summary_execute("2020-01")
    assert result['succeeded'] == 3


@pytest.mark.django_db
def test__create_monthly_summary__異常系__日付のフォーマットが違う場合():
    AccountFactory.create_batch(3)
    with pytest.raises(ValueError):
        tasks.create_monthly_account_storage_summary_execute("2020-01-01")
