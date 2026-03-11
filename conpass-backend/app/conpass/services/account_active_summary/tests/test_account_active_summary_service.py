import datetime
import itertools

import freezegun
import pytest
from django.utils.timezone import make_aware

from conpass.models import Account, File, AccountActiveSummary, Contract
from conpass.services.account_active_summary.account_active_summary_service import AccountActiveSummaryService
from conpass.tests.factories.account import AccountFactory
from conpass.tests.factories.account_active_summary import AccountActiveSummaryFactory
from conpass.tests.factories.contract import ContractFactory


@pytest.fixture
def service():
    return AccountActiveSummaryService()


@pytest.fixture
def today():
    with freezegun.freeze_time('2020-01-01'):
        return make_aware(datetime.datetime.now()).today()


class TestAccountActiveSummaryServiceCreateDailySummary:

    @pytest.mark.django_db
    def test__create_daily_summary__アクティブ契約数(self, service, today):
        account: Account = AccountFactory()
        for contract_type, status in itertools.product(
            [x.value for x in Contract.ContractType],
            [x.value for x in Contract.Status],
        ):
            ContractFactory.create(
                account=account,
                type=contract_type,
                status=status,
            )

        actual: AccountActiveSummary = service.create_daily_summary(account=account, date=today)

        assert actual.active_contracts_count == 1 * 9, "ContractType.CONTRACT かつ Status.DISABLE以外"
        assert actual.date_from.strftime('%Y-%m-%d') == '2020-01-01'
        assert actual.date_to.strftime('%Y-%m-%d') == '2020-01-01'


class TestAccountActiveSummaryServiceCreateMonthlySummary:
    """create_month_summary"""

    @pytest.mark.django_db
    def test__create_monthly_summary(self, service):
        account: Account = AccountFactory()
        AccountActiveSummaryFactory.create(
            account=account,
            cycle=AccountActiveSummary.Cycle.DAILY.value,
            date_from=datetime.date(2000, 1, 1),
            active_contracts_count=1000,
        )
        AccountActiveSummaryFactory.create(
            account=account,
            cycle=AccountActiveSummary.Cycle.DAILY.value,
            date_from=datetime.date(2000, 1, 15),
            active_contracts_count=1002,
        )
        AccountActiveSummaryFactory.create(
            account=account,
            cycle=AccountActiveSummary.Cycle.DAILY.value,
            date_from=datetime.date(2000, 1, 31),
            active_contracts_count=1001,
        )
        AccountActiveSummaryFactory.create(
            account=account,
            cycle=AccountActiveSummary.Cycle.DAILY.value,
            date_from=datetime.date(1999, 12, 1),
            active_contracts_count=2000,
        )
        AccountActiveSummaryFactory.create(
            account=account,
            cycle=AccountActiveSummary.Cycle.DAILY.value,
            date_from=datetime.date(1999, 1, 1),
            active_contracts_count=3000,
        )

        actual: AccountActiveSummary = service.create_monthly_summary(account=account, month=datetime.date(2000, 1, 1))

        assert actual.cycle == AccountActiveSummary.Cycle.MONTHLY.value
        assert actual.active_contracts_count == 1002
        assert actual.date_from.strftime('%Y-%m-%d') == '2000-01-01'
        assert actual.date_to.strftime('%Y-%m-%d') == '2000-01-31'


class TestAccountActiveSummaryServiceListMonthlySummary:
    """list_month_summary"""

    @pytest.mark.django_db
    def test__正常系(self, service):
        account: Account = AccountFactory()
        AccountActiveSummaryFactory.create(
            account=account,
            cycle=AccountActiveSummary.Cycle.MONTHLY.value,
            date_from=datetime.date(2000, 6, 1),
            active_contracts_count=1000,
        )
        AccountActiveSummaryFactory.create(
            account=account,
            cycle=AccountActiveSummary.Cycle.MONTHLY.value,
            date_from=datetime.date(2000, 7, 1),
            active_contracts_count=2000,
        )
        AccountActiveSummaryFactory.create(
            account=account,
            cycle=AccountActiveSummary.Cycle.MONTHLY.value,
            date_from=datetime.date(2000, 8, 1),
            active_contracts_count=3000,
        )

        actual = service.list_monthly_summary(
            account=account,
            month_from=datetime.date(2000, 4, 1),
            month_to=datetime.date(2000, 8, 1),
        )

        assert len(actual) == 5

    @pytest.mark.django_db
    @freezegun.freeze_time('2000-02-15')
    def test__過去の集計の存在しない月は0を返すこと(self, service):
        account: Account = AccountFactory()
        actual = service.list_monthly_summary(
            account=account,
            month_from=datetime.date(2000, 2, 1),
            month_to=datetime.date(2000, 2, 1),
        )

        assert actual[0].cycle == AccountActiveSummary.Cycle.MONTHLY.value
        assert actual[0].date_from == datetime.date(2000, 2, 1)
        assert actual[0].date_to == datetime.date(2000, 2, 29)
        assert actual[0].active_contracts_count == 0

    @pytest.mark.django_db
    @freezegun.freeze_time('2000-02-15')
    def test__今月は現在のContractから集計して結果を返すこと(self, service):
        account: Account = AccountFactory()
        ContractFactory.create_batch(
            3,
            account=account,
            type=Contract.ContractType.CONTRACT.value,
            status=Contract.Status.ENABLE.value,
        )
        actual = service.list_monthly_summary(
            account=account,
            month_from=datetime.date(2000, 2, 1),
            month_to=datetime.date(2000, 2, 1),
        )

        assert actual[0].cycle == AccountActiveSummary.Cycle.MONTHLY.value
        assert actual[0].date_from == datetime.date(2000, 2, 1)
        assert actual[0].date_to == datetime.date(2000, 2, 29)
        assert actual[0].active_contracts_count == 3
