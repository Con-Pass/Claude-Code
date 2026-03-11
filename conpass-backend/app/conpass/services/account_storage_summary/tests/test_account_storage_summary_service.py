import datetime

import freezegun
import pytest
from django.utils.timezone import make_aware

from conpass.models import Account, File, AccountStorageSummary
from conpass.services.account_storage_summary.account_storage_summary_service import AccountStorageSummaryService
from conpass.tests.factories.account import AccountFactory
from conpass.tests.factories.account_storage_summary import AccountStorageSummaryFactory
from conpass.tests.factories.file import FileFactory


@pytest.fixture
def service():
    return AccountStorageSummaryService()


@pytest.fixture
def today():
    with freezegun.freeze_time('2020-01-01'):
        return make_aware(datetime.datetime.now()).today()


class TestAccountStorageSummaryServiceCreateDailySummary:

    @pytest.mark.django_db
    def test__create_daily_summary__ファイル数(self, service, today):
        account: Account = AccountFactory()
        FileFactory.create_batch(20, account=account)

        actual: AccountStorageSummary = service.create_daily_summary(account=account, date=today)

        assert actual.file_num == 20
        assert actual.date_from.strftime('%Y-%m-%d') == '2020-01-01'
        assert actual.date_to.strftime('%Y-%m-%d') == '2020-01-01'

    @pytest.mark.django_db
    def test__create_daily_summary__ファイルサイズ(self, service, today):
        account: Account = AccountFactory()
        FileFactory.create(account=account, size=1000)
        FileFactory.create(account=account, size=2000)
        FileFactory.create(account=account, size=3000)
        FileFactory.create(account=account, size=4000, status=File.Status.DISABLE.value)
        FileFactory.create(account=AccountFactory(), size=5000)

        actual: AccountStorageSummary = service.create_daily_summary(account=account, date=today)

        assert actual.file_size_total == 6000


class TestAccountStorageSummaryServicePutMonthlySummary:
    """create_month_summary"""

    @pytest.mark.django_db
    def test__日次のサマリーのうち最もファイルサイズの大きい値を使う(self, service):
        account: Account = AccountFactory()
        AccountStorageSummaryFactory.create(
            account=account,
            cycle=AccountStorageSummary.Cycle.DAILY.value,
            date_from=datetime.date(2000, 1, 1),
            file_size_total=1000,
        )
        AccountStorageSummaryFactory.create(
            account=account,
            cycle=AccountStorageSummary.Cycle.DAILY.value,
            date_from=datetime.date(2000, 1, 15),
            file_size_total=1002,
        )
        AccountStorageSummaryFactory.create(
            account=account,
            cycle=AccountStorageSummary.Cycle.DAILY.value,
            date_from=datetime.date(2000, 1, 31),
            file_size_total=1001,
        )
        AccountStorageSummaryFactory.create(
            account=account,
            cycle=AccountStorageSummary.Cycle.DAILY.value,
            date_from=datetime.date(1999, 12, 31),
            file_size_total=2000,
        )
        AccountStorageSummaryFactory.create(
            account=account,
            cycle=AccountStorageSummary.Cycle.DAILY.value,
            date_from=datetime.date(1999, 1, 31),
            file_size_total=3000,
        )

        actual: AccountStorageSummary = service.create_monthly_summary(account=account, month=datetime.date(2000, 1, 1))

        assert actual.cycle == AccountStorageSummary.Cycle.MONTHLY.value
        assert actual.file_size_total == 1002
        assert actual.date_from.strftime('%Y-%m-%d') == '2000-01-01'
        assert actual.date_to.strftime('%Y-%m-%d') == '2000-01-31'


class TestAccountStorageSummaryServiceListMonthlySummary:
    """list_month_summary"""

    @pytest.mark.django_db
    def test__正常系(self, service):
        account: Account = AccountFactory()
        AccountStorageSummaryFactory.create(
            account=account,
            cycle=AccountStorageSummary.Cycle.MONTHLY.value,
            date_from=datetime.date(2000, 6, 1),
            file_size_total=1000,
        )
        AccountStorageSummaryFactory.create(
            account=account,
            cycle=AccountStorageSummary.Cycle.MONTHLY.value,
            date_from=datetime.date(2000, 7, 1),
            file_size_total=2000,
        )
        AccountStorageSummaryFactory.create(
            account=account,
            cycle=AccountStorageSummary.Cycle.MONTHLY.value,
            date_from=datetime.date(2000, 8, 1),
            file_size_total=3000,
        )

        actual = service.list_monthly_summary(
            account=account,
            month_from=datetime.date(2000, 4, 1),
            month_to=datetime.date(2000, 9, 1),
        )

        assert len(actual) == 6

    @pytest.mark.django_db
    @freezegun.freeze_time('2000-02-15')
    def test__過去の集計の存在しない月は0を返すこと(self, service):
        account: Account = AccountFactory()
        actual = service.list_monthly_summary(
            account=account,
            month_from=datetime.date(2000, 2, 1),
            month_to=datetime.date(2000, 2, 1),
        )

        assert actual[0].cycle == AccountStorageSummary.Cycle.MONTHLY.value
        assert actual[0].date_from == datetime.date(2000, 2, 1)
        assert actual[0].date_to == datetime.date(2000, 2, 29)
        assert actual[0].file_size_total == 0
        assert actual[0].file_num == 0

    @pytest.mark.django_db
    @freezegun.freeze_time('2000-02-15')
    def test__今月は現在のFileから集計して結果を返すこと(self, service):
        account: Account = AccountFactory()
        FileFactory.create(account=account, size=100)
        FileFactory.create(account=account, size=200)
        actual = service.list_monthly_summary(
            account=account,
            month_from=datetime.date(2000, 2, 1),
            month_to=datetime.date(2000, 2, 1),
        )

        assert actual[0].cycle == AccountStorageSummary.Cycle.MONTHLY.value
        assert actual[0].date_from == datetime.date(2000, 2, 1)
        assert actual[0].date_to == datetime.date(2000, 2, 29)
        assert actual[0].file_size_total == 300
        assert actual[0].file_num == 2
