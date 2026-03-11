import datetime
import random
from logging import getLogger

import django.db
from celery.result import AsyncResult
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.management.base import BaseCommand

from common.utils import date_utils
from conpass.models import Account, AccountStorageSummary, AccountActiveSummary
from conpass.services.account_active_summary.account_active_summary_service import AccountActiveSummaryService
from conpass.services.account_active_summary.tasks import create_daily_account_active_summary

logger = getLogger(__name__)


class Command(BaseCommand):
    help = 'Create fake account summaries'

    def __init__(self):
        super().__init__()
        self.service = AccountActiveSummaryService()

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        if not settings.DEBUG:
            logger.error('本番環境で実行することはできません')

        today = datetime.date.today()
        this_month = date_utils.get_first_day_of_month(today)
        for account in Account.objects.all():
            for i in range(5, 0, -1):
                month = this_month - relativedelta(months=i)
                try:
                    storage = AccountStorageSummary(
                        account=account,
                        file_size_total=random.randint(10_000_000, 10_000_000_000),
                        file_num=random.randint(10, 1000),
                        cycle=AccountStorageSummary.Cycle.MONTHLY.value,
                        date_from=month,
                        date_to=date_utils.get_last_day_of_month(month),
                    )
                    storage.save()

                    active = AccountActiveSummary(
                        account=account,
                        active_contracts_count=random.randint(10, 1000),
                        cycle=AccountStorageSummary.Cycle.MONTHLY.value,
                        date_from=month,
                        date_to=date_utils.get_last_day_of_month(month),
                    )
                    active.save()
                except django.db.IntegrityError as e:
                    code = e.args[0]
                    if code == 1062:
                        logger.info(
                            f"既に存在するためスキップします: account_id={account.id} month={month.strftime('%Y-%m')}")
                    else:
                        raise e
