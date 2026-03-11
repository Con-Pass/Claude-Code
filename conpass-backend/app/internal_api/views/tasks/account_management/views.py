from logging import getLogger
from typing import Union

from celery.result import AsyncResult
from django.http import HttpRequest
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.services.account_management import tasks
from internal_api.views.utils.decorators import log_internal_api

logger = getLogger(__name__)


class InternalApiTasksActivateAccountView(APIView):
    permission_classes = []

    @log_internal_api
    def post(self, request: Union[Request, HttpRequest]):
        task_result: AsyncResult = tasks.activate_account.delay()
        return Response({
            'task_id': task_result.task_id,
            'task_status': task_result.status,
        })


class PrivateApiExecuteActiveAccountView(APIView):
    permission_classes = []

    def post(self, request):
        ret = tasks.activate_account_execute()
        return Response({'result': ret})


class InternalApiTasksInvalidateAccountView(APIView):
    permission_classes = []

    @log_internal_api
    def post(self, request: Union[Request, HttpRequest]):
        task_result: AsyncResult = tasks.invalidate_account.delay()
        return Response({
            'task_id': task_result.task_id,
            'task_status': task_result.status,
        })


class PrivateApiExecuteInvalidateAccountView(APIView):
    permission_classes = []

    def post(self, request):
        ret = tasks.invalidate_account_execute()
        return Response({'result': ret})
