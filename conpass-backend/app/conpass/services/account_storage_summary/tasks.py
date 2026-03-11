import datetime
import threading
from logging import getLogger

from celery import shared_task
from django.utils.timezone import make_aware
from django.conf import settings

from conpass.services.account_storage_summary.account_storage_summary_service import AccountStorageSummaryService
from conpass.services.account_summary.summarize_service import execute_summarize_every_account

from common.utils.http_utils import execute_http_post

logger = getLogger('celery')


@shared_task
def create_daily_account_storage_summary(date_string: str):
    """
    date: YYYY-MM-DD
    """
    def execute(d_str):
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/create-daily-account-storage-summary'
            data = {'dateString': d_str}
            execute_http_post(url, data)
        except Exception as e:
            logger.error(f"create_daily_account_storage_summary execute request error: {e}")

    thread = threading.Thread(target=execute, args=(date_string,))
    thread.start()
    return True


def create_daily_account_storage_summary_execute(date_string: str):
    """
    date: YYYY-MM-DD
    """
    date = make_aware(datetime.datetime.strptime(date_string, '%Y-%m-%d')).date()
    service = AccountStorageSummaryService()
    return execute_summarize_every_account(service.create_daily_summary, date=date).to_dict()


@shared_task
def create_monthly_account_storage_summary(month_string: str):
    """
    date: YYYY-MM
    """
    def execute(m_str):
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/create-monthly-account-storage-summary'
            data = {'monthString': m_str}
            execute_http_post(url, data)
        except Exception as e:
            logger.error(f"create_monthly_account_storage_summary execute request error: {e}")

    thread = threading.Thread(target=execute, args=(month_string,))
    thread.start()
    return True


def create_monthly_account_storage_summary_execute(month_string: str):
    """
    date: YYYY-MM
    """
    month = make_aware(datetime.datetime.strptime(month_string, '%Y-%m')).date()
    service = AccountStorageSummaryService()
    return execute_summarize_every_account(service.create_monthly_summary, month=month).to_dict()
