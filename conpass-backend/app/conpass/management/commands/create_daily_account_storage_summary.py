from logging import getLogger

from celery.result import AsyncResult
from django.core.management.base import BaseCommand

from conpass.services.account_storage_summary.account_storage_summary_service import AccountStorageSummaryService
from conpass.services.account_storage_summary.tasks import create_daily_account_storage_summary

logger = getLogger(__name__)


class Command(BaseCommand):
    help = 'Create daily account storage summaries'

    def __init__(self):
        super().__init__()
        self.service = AccountStorageSummaryService()

    def add_arguments(self, parser):
        parser.add_argument('date', type=str, help='YYYY-MM-DD')

    def handle(self, *args, **options):
        async_result: AsyncResult = create_daily_account_storage_summary.delay(options['date'])
        logger.info(f'task_id: {async_result.task_id}')
