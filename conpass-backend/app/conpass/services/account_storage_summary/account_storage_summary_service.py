import datetime
from dateutil import relativedelta
from typing import List

import django.db.models

from common.utils import date_utils
from conpass.models import Account, File

from conpass.models import AccountStorageSummary


class AccountStorageSummaryService:
    def create_daily_summary(self, account: Account, date: datetime.date) -> AccountStorageSummary:
        summary = self._make_daily_summary(account=account, date=date)
        summary.save()
        return summary

    def _make_daily_summary(self, account: Account, date: datetime.date) -> AccountStorageSummary:
        aggregate = (
            File.objects.filter(
                account=account,
                status=File.Status.ENABLE.value,
            ).aggregate(
                django.db.models.Sum('size'),
                django.db.models.Count('id'),
            )
        )
        summary = AccountStorageSummary(
            account=account,
            file_size_total=aggregate['size__sum'] or 0,
            file_num=aggregate['id__count'] or 0,
            cycle=AccountStorageSummary.Cycle.DAILY.value,
            date_from=date,
            date_to=date,
        )
        return summary

    def create_monthly_summary(self, account: Account, month: datetime.date) -> AccountStorageSummary:
        aggregate = (
            AccountStorageSummary.objects.filter(
                account=account,
                date_from__year=month.year,
                date_from__month=month.month,
            ).aggregate(
                django.db.models.Max('file_size_total'),
                django.db.models.Max('file_num'),
            )
        )

        summary = AccountStorageSummary(
            account=account,
            file_size_total=aggregate['file_size_total__max'] or 0,
            file_num=aggregate['file_num__max'] or 0,
            cycle=AccountStorageSummary.Cycle.MONTHLY.value,
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
    ) -> List[AccountStorageSummary]:
        assert month_from.day == 1, "month_from must be first day of the month"
        assert month_to.day == 1, "month_to must be first day of the month"
        assert month_from <= month_to, "month_to must be greater than or equal month_from"
        summaries = AccountStorageSummary.objects.filter(
            account=account,
            cycle=AccountStorageSummary.Cycle.MONTHLY.value,
            date_from__gte=month_from,
            date_from__lte=month_to,
        ).order_by('date_from').all()

        return self._fill_monthly_summary(account, summaries, month_from, month_to)

    def _fill_monthly_summary(
        self,
        account: Account,
        summaries: List[AccountStorageSummary],
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
                summary = self._make_daily_summary(account, date=today)
                summary.cycle = AccountStorageSummary.Cycle.MONTHLY.value
                summary.date_from = date_utils.get_first_day_of_month(today)
                summary.date_to = date_utils.get_last_day_of_month(today)
                ret.append(summary)
            else:
                # 集計がない場合はカウント0のダミーデータを返す
                ret.append(AccountStorageSummary(
                    account=account,
                    file_size_total=0,
                    file_num=0,
                    cycle=AccountStorageSummary.Cycle.MONTHLY.value,
                    date_from=current_month,
                    date_to=date_utils.get_last_day_of_month(current_month),
                ))
            current_month += relativedelta.relativedelta(months=1)
        return ret
