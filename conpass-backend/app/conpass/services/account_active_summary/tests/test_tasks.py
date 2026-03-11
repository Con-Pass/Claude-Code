import pytest

from conpass.services.account_active_summary import tasks
from conpass.tests.factories.account import AccountFactory
from conpass.tests.factories.account_active_summary import AccountActiveSummaryFactory


@pytest.mark.django_db
def test__create_daily_account_active_summary():
    AccountFactory.create_batch(3)
    result = tasks.create_daily_account_active_summary_execute('2022-01-01')
    assert result['succeeded'] == 3


@pytest.mark.django_db
def test__create_monthly_account_active_summary__正常系():
    account1 = AccountFactory.create()
    AccountFactory.create()
    AccountActiveSummaryFactory.create(account=account1)
    result = tasks.create_monthly_account_active_summary_execute('2022-01')
    assert result['succeeded'] == 2


@pytest.mark.django_db
def test__create_monthly_account_active_summary__異常系__YYYY_MMではない場合():
    account1 = AccountFactory.create()
    AccountActiveSummaryFactory.create(account=account1)
    with pytest.raises(ValueError):
        tasks.create_monthly_account_active_summary_execute('2022-01-01')
