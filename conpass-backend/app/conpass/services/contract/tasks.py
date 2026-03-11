import json

import requests
import threading
from logging import getLogger

from celery import shared_task
from django.core.management import call_command
from django.conf import settings
from conpass.services.contract.contract_service import ContractService
from config.celery import app
from common.utils.http_utils import execute_http_post


logger = getLogger('celery')


@shared_task
def expire_contract():

    def execute():
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/expire-contract'
            execute_http_post(url, None)
        except Exception as e:
            logger.error(f"expire_contract execute request error: {e}")

    thread = threading.Thread(target=execute)
    thread.start()
    return True


def expire_contract_execute():
    service = ContractService()
    return service.expire_contract()


@shared_task
def create_search_body_task():

    def execute():
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/create-search-body-task'
            execute_http_post(url, None)
        except Exception as e:
            logger.error(f"create_search_body_task execute request error: {e}")

    thread = threading.Thread(target=execute)
    thread.start()
    return True


def create_search_body_task_execute():
    call_command('create_search_body')


@shared_task
def send_contract_renew_mail_task():

    def execute():
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/send-contract-renew-mail-task'
            execute_http_post(url, None)
        except Exception as e:
            logger.error(f"send_contract_renew_mail_task execute request error: {e}")

    thread = threading.Thread(target=execute)
    thread.start()
    return True


def send_contract_renew_mail_task_execute():
    call_command('send_contract_renew_mail')


@app.task(bind=True, name="notify_to_AI_agent")
def notify_to_AI_agent(self, contract_ids: list, event_type:str):
    logger.info(f"Agent notification received for contract ids: {contract_ids}, event type: {event_type} ")
    try:
        url = settings.AI_AGENT_WEBHOOK_ENDPOINT
        if url:
            headers = {
                'x-api-key': settings.AI_AGENT_WEBHOOK_API_KEY,
                'Content-Type': 'application/json'
            }
            data={
                'contract_ids': contract_ids,
                'event_type': event_type
            }
            response = requests.post(url, data=json.dumps(data), headers=headers)
            if response.status_code in  [200, 201]:
                logger.info(
                    f"notify_to_AI_agent execute request success: {response.status_code}, contract ids: {contract_ids}, event type: {event_type}")
            else:
                logger.error(f"notify_to_AI_agent execute request error: {response.status_code}, response: {response.text[:100]}")


    except Exception as e:
        logger.error(f"notify_to_AI_agent execute request error: {e}")



