import datetime
import threading
from logging import getLogger

from celery import shared_task
from django.utils.timezone import make_aware
from django.conf import settings

from conpass.services.file_upload_status.check_upload_result_service import CheckUploadResultService

from common.utils.http_utils import execute_http_post

logger = getLogger('celery')


@shared_task
def check_upload_result(date_string: str):
    """
    date: YYYY-MM-DD
    """
    def execute(d_str):
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/check-upload-result'
            data = {'dateString': d_str}
            execute_http_post(url, data)
        except Exception as e:
            logger.error(f"check_upload_result execute request error: {e}")

    thread = threading.Thread(target=execute, args=(date_string,))
    thread.start()
    return True


def check_upload_result_execute(date_string: str):
    """
    date: YYYY-MM-DD
    """
    date = make_aware(datetime.datetime.strptime(date_string, '%Y-%m-%d')).date()
    service = CheckUploadResultService()
    return service.check_upload_result(date=date)


@shared_task
def clean_failed_uploads(date_string: str):
    """
    date: YYYY-MM-DD
    """
    def execute(d_str):
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/clean-failed-uploads'
            data = {'dateString': d_str}
            execute_http_post(url, data)
        except Exception as e:
            logger.error(f"clean_failed_uploads execute request error: {e}")

    thread = threading.Thread(target=execute, args=(date_string,))
    thread.start()
    return True


def clean_failed_uploads_execute(date_string: str):
    """
    date: YYYY-MM-DD
    """
    date = make_aware(datetime.datetime.strptime(date_string, '%Y-%m-%d')).date()
    service = CheckUploadResultService()
    return service.clean_failed_uploads(date=date)
