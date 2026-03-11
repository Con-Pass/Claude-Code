import datetime
from logging import getLogger
from typing import Union

from celery.result import AsyncResult
from dateutil.relativedelta import relativedelta
from django.http import HttpRequest
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.utils import date_utils
from conpass.services.account_storage_summary import tasks
from internal_api.views.utils.decorators import log_internal_api
from internal_api.views.tasks.account_storage_summary.account_storage_summary_serializer \
    import PrivateApiExecuteAccountStorageSummaryDailyRequestBodySerializer, PrivateApiExecuteAccountStorageSummaryMonthlyRequestBodySerializer

logger = getLogger(__name__)


class InternalApiTasksAccountStorageSummaryDailyView(APIView):
    permission_classes = []

    @log_internal_api
    def post(self, request: Union[Request, HttpRequest]):
        yesterday = datetime.date.today() - relativedelta(days=1)
        task_result: AsyncResult = tasks.create_daily_account_storage_summary.delay(yesterday.strftime('%Y-%m-%d'))
        return Response({
            'task_id': task_result.task_id,
            'task_status': task_result.status,
        })


class PrivateApiExecuteAccountStorageSummaryDailyView(APIView):
    permission_classes = []

    def post(self, request):
        req_serializer = PrivateApiExecuteAccountStorageSummaryDailyRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data
        date_string = data.get('dateString')

        ret = tasks.create_daily_account_storage_summary_execute(date_string)
        return Response(ret)


class InternalApiTasksAccountStorageSummaryMonthlyView(APIView):
    permission_classes = []

    @log_internal_api
    def post(self, request: Union[Request, HttpRequest]):
        last_month = date_utils.get_first_day_of_month(datetime.date.today()) - relativedelta(months=1)
        task_result: AsyncResult = tasks.create_monthly_account_storage_summary.delay(last_month.strftime('%Y-%m'))
        return Response({
            'task_id': task_result.task_id,
            'task_status': task_result.status,
        })


class PrivateApiExecuteAccountStorageSummaryMonthlyView(APIView):
    permission_classes = []

    def post(self, request):
        req_serializer = PrivateApiExecuteAccountStorageSummaryMonthlyRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data
        month_string = data.get('monthString')

        ret = tasks.create_monthly_account_storage_summary_execute(month_string)
        return Response(ret)
