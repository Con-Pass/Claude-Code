from logging import getLogger

from celery.result import AsyncResult
from django.core.management.base import BaseCommand


logger = getLogger(__name__)


class Command(BaseCommand):
    help = 'confirm_task_status'

    def __init__(self):
        super().__init__()

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):

        task_id = ""  # 実際のタスクIDに置き換えてください
        result = AsyncResult(task_id)

        print(result.state)
        print(result.result)
