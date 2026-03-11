from logging import getLogger

from celery.result import AsyncResult
from django.core.management.base import BaseCommand

from conpass.services.contract.contract_service import ContractService
from conpass.services.contract.tasks import expire_contract

logger = getLogger(__name__)


class Command(BaseCommand):
    help = 'Contract expire'

    def __init__(self):
        super().__init__()
        self.service = ContractService()

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        async_result: AsyncResult = expire_contract.delay()
        logger.info(f'task_id: {async_result.task_id}')
