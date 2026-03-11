import datetime

from dateutil.relativedelta import relativedelta
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from djangorestframework_camel_case.render import CamelCaseJSONRenderer

from common.utils import date_utils
from conpass.services.account_storage_summary.account_storage_summary_service import AccountStorageSummaryService
from conpass.views.account_storage_summary.serializer.account_storage_summary_serializer import \
    AccountStorageSummarySerializer


class AccountStorageSummaryListView(APIView):
    renderer_classes = [
        CamelCaseJSONRenderer,
        BrowsableAPIRenderer,
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = AccountStorageSummaryService()

    def get(self, request):
        this_month = date_utils.get_first_day_of_month(datetime.date.today())
        # 過去12ヶ月
        summaries = self.service.list_monthly_summary(
            account=request.user.account,
            month_from=this_month - relativedelta(months=11),
            month_to=this_month,
        )

        response = AccountStorageSummarySerializer(summaries, many=True)
        return Response(data=response.data)
