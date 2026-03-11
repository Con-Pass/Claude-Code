import datetime
from dateutil import relativedelta
from typing import List

import django.db.models

from common.utils import date_utils
from conpass.models import Account, Contract

from conpass.models import AccountActiveSummary


class AccountActiveSummaryService:
    def create_daily_summary(self, account: Account, date: datetime.date) -> AccountActiveSummary:
        summary = self._make_daily_summary(account=account, date=date)
        summary.save()
        return summary

    def _make_daily_summary(self, account: Account, date: datetime.date) -> AccountActiveSummary:
        aggregate = (
            Contract.objects.filter(
                account=account,
                type=Contract.ContractType.CONTRACT.value,
            ).exclude(
                status=Contract.Status.DISABLE.value,
            ).aggregate(
                django.db.models.Count('id'),
            )
        )

        summary = AccountActiveSummary(
            account=account,
            cycle=AccountActiveSummary.Cycle.DAILY.value,
            active_contracts_count=aggregate['id__count'] or 0,
            date_from=date,
            date_to=date,
        )
        return summary

    def create_monthly_summary(self, account: Account, month: datetime.date) -> AccountActiveSummary:
        aggregate = (
            AccountActiveSummary.objects.filter(
                account=account,
                date_from__year=month.year,
                date_from__month=month.month,
            ).aggregate(
                django.db.models.Max('active_contracts_count'),
            )
        )

        summary = AccountActiveSummary(
            account=account,
            active_contracts_count=aggregate['active_contracts_count__max'] or 0,
            cycle=AccountActiveSummary.Cycle.MONTHLY.value,
            date_from=date_utils.get_first_day_of_month(month),
            date_to=date_utils.get_last_day_of_month(month),
        )
        summary.save()
        return summary

    def list_monthly_summary(
        self,
        account: Account,
        month_from: datetime.date,
        month_to: datetime.date
    ) -> List[AccountActiveSummary]:
        assert month_from.day == 1, "month_from must be first day of the month"
        assert month_to.day == 1, "month_to must be first day of the month"
        assert month_from <= month_to, "month_to must be greater than or equal month_from"
        summaries = AccountActiveSummary.objects.filter(
            account=account,
            cycle=AccountActiveSummary.Cycle.MONTHLY.value,
            date_from__gte=month_from,
            date_from__lte=month_to,
        ).order_by('date_from').all()

        return self._fill_monthly_summary(account, summaries, month_from, month_to)

    def _fill_monthly_summary(
        self,
        account: Account,
        summaries: List[AccountActiveSummary],
        month_from: datetime.date,
        month_to: datetime.date,
    ):
        key_format = '%Y%m%d'
        mapping = {summary.date_from.strftime(key_format): summary for summary in summaries}
        ret = []
        current_month = month_from
        while current_month <= month_to:
            if (key := current_month.strftime(key_format)) in mapping:
                ret.append(mapping[key])
            elif current_month.month == (today := datetime.date.today()).month:
                # 今月の場合はリアルタイムに集計する
                summary = self._make_daily_summary(account=account, date=today)
                summary.cycle = AccountActiveSummary.Cycle.MONTHLY.value
                summary.date_from = date_utils.get_first_day_of_month(today)
                summary.date_to = date_utils.get_last_day_of_month(today)
                ret.append(summary)
            else:
                # 集計がない場合はカウント0のダミーデータを返す
                ret.append(AccountActiveSummary(
                    account=account,
                    active_contracts_count=0,
                    cycle=AccountActiveSummary.Cycle.MONTHLY.value,
                    date_from=current_month,
                    date_to=date_utils.get_last_day_of_month(current_month),
                ))
            current_month += relativedelta.relativedelta(months=1)
        return ret
