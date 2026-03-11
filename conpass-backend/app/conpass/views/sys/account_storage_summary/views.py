import datetime

from dateutil.relativedelta import relativedelta
from rest_framework import status
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.response import Response
from djangorestframework_camel_case.render import CamelCaseJSONRenderer

from common.utils import date_utils
from conpass.models import Account
from conpass.services.account_storage_summary.account_storage_summary_service import AccountStorageSummaryService
from conpass.views.account_storage_summary.serializer.account_storage_summary_serializer import \
    AccountStorageSummarySerializer
from conpass.views.sys.common import SysAPIView


class SysAccountStorageSummaryListView(SysAPIView):
    renderer_classes = [
        CamelCaseJSONRenderer,
        BrowsableAPIRenderer,
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = AccountStorageSummaryService()

    def get(self, request, account_id: int):

        this_month = date_utils.get_first_day_of_month(datetime.date.today())
        try:
            account = Account.objects.filter(id=account_id).get()
        except Account.DoesNotExist:
            return Response("Not found resource.", status=status.HTTP_404_NOT_FOUND)

        # 過去12ヶ月
        summaries = self.service.list_monthly_summary(
            account=account,
            month_from=this_month - relativedelta(months=11),
            month_to=this_month,
        )

        response = AccountStorageSummarySerializer(summaries, many=True)
        return Response(data=response.data)
