from logging import getLogger
from typing import Union

from celery.result import AsyncResult
from django.http import HttpRequest
from django.core.management import call_command
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.services.contract import tasks
from internal_api.views.utils.decorators import log_internal_api

logger = getLogger(__name__)


class InternalApiTasksExpireContractView(APIView):
    permission_classes = []

    @log_internal_api
    def post(self, request: Union[Request, HttpRequest]):
        task_result: AsyncResult = tasks.expire_contract.delay()
        return Response({
            'task_id': task_result.task_id,
            'task_status': task_result.status,
        })


class PrivateApiExecuteExpireContractView(APIView):
    permission_classes = []

    def post(self, request):
        ret = tasks.expire_contract_execute()
        return Response({'result': ret})


class InternalApiTasksContractBodySearchSaveView(APIView):
    permission_classes = []

    @log_internal_api
    def post(self, request, *args, **kwargs):
        task_result: AsyncResult = tasks.create_search_body_task.delay()
        return Response({
            'task_id': task_result.task_id,
            'task_status': task_result.status,
        })


class PrivateApiExecuteContractBodySearchSaveView(APIView):
    permission_classes = []

    def post(self, request):
        ret = tasks.create_search_body_task_execute()
        return Response({'result': ret})


class InternalApiTasksSendContractRenewMailView(APIView):
    permission_classes = []

    @log_internal_api
    def post(self, request, *args, **kwargs):
        task_result: AsyncResult = tasks.send_contract_renew_mail_task.delay()
        return Response({
            'task_id': task_result.task_id,
            'task_status': task_result.status,
        })


class PrivateApiExecuteSendC0jtractRenewMailView(APIView):
    permission_classes = []

    def post(self, request):
        ret = tasks.send_contract_renew_mail_task_execute()
        return Response({'result': ret})
