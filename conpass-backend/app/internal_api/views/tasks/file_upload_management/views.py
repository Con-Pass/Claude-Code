import datetime
from dateutil.relativedelta import relativedelta
from logging import getLogger
from typing import Union

from celery.result import AsyncResult
from django.http import HttpRequest
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.services.file_upload_status import tasks
from internal_api.views.utils.decorators import log_internal_api
from internal_api.views.tasks.file_upload_management.file_upload_management_serializer \
    import PrivateApiExecuteCheckUploadResultRequestBodySerializer, PrivateApiExecuteCleanFailedUploadsRequestBodySerializer

logger = getLogger(__name__)


class InternalApiTasksCheckUploadResultView(APIView):
    permission_classes = []

    @log_internal_api
    def post(self, request: Union[Request, HttpRequest]):
        yesterday = datetime.date.today() - relativedelta(days=1)
        task_result: AsyncResult = tasks.check_upload_result.delay(yesterday.strftime('%Y-%m-%d'))
        return Response({
            'task_id': task_result.task_id,
            'task_status': task_result.status,
        })


class PrivateApiExecuteCheckUploadResultView(APIView):
    permission_classes = []

    def post(self, request):
        req_serializer = PrivateApiExecuteCheckUploadResultRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data
        date_string = data.get('dateString')

        ret = tasks.check_upload_result_execute(date_string)
        return Response(ret)


class InternalApiTasksCleanFailedUploadsView(APIView):
    permission_classes = []

    @log_internal_api
    def post(self, request: Union[Request, HttpRequest]):
        yesterday = datetime.date.today() - relativedelta(days=1)
        task_result: AsyncResult = tasks.clean_failed_uploads.delay(yesterday.strftime('%Y-%m-%d'))
        return Response({
            'task_id': task_result.task_id,
            'task_status': task_result.status,
        })


class PrivateApiExecuteCleanFailedUploadsView(APIView):
    permission_classes = []

    def post(self, request):
        req_serializer = PrivateApiExecuteCleanFailedUploadsRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data
        date_string = data.get('dateString')

        ret = tasks.clean_failed_uploads_execute(date_string)
        return Response(ret)
