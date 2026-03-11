import requests
import threading
from logging import getLogger

from celery import shared_task

from django.conf import settings

from conpass.services.account_management.account_management_service import AccountManagementService

from common.utils.http_utils import execute_http_post

logger = getLogger('celery')


@shared_task
def activate_account():

    def execute():
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/activate-account'
            execute_http_post(url, None)
        except Exception as e:
            logger.error(f"activate_account execute request error: {e}")

    thread = threading.Thread(target=execute)
    thread.start()
    return True


def activate_account_execute():
    service = AccountManagementService()
    return service.activate_account()


@shared_task
def invalidate_account():

    def execute():
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/invalidate-account'
            execute_http_post(url, None)
        except Exception as e:
            logger.error(f"invalidate_account execute request error: {e}")

    thread = threading.Thread(target=execute)
    thread.start()
    return True


def invalidate_account_execute():
    service = AccountManagementService()
    return service.invalidate_account()
