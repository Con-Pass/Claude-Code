from logging import getLogger

from celery.result import AsyncResult
from django.core.management.base import BaseCommand

from conpass.services.account_active_summary.account_active_summary_service import AccountActiveSummaryService
from conpass.services.account_active_summary.tasks import create_monthly_account_active_summary

logger = getLogger(__name__)


class Command(BaseCommand):
    help = 'Create monthly account active summaries'

    def __init__(self):
        super().__init__()
        self.service = AccountActiveSummaryService()

    def add_arguments(self, parser):
        parser.add_argument('month', type=str, help='YYYY-MM')

    def handle(self, *args, **options):
        async_result: AsyncResult = create_monthly_account_active_summary.delay(options['month'])
        logger.info(f'task_id: {async_result.task_id}')
