import datetime

from dateutil.relativedelta import relativedelta
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from djangorestframework_camel_case.render import CamelCaseJSONRenderer

from common.utils import date_utils
from conpass.services.account_active_summary.account_active_summary_service import AccountActiveSummaryService
from conpass.views.account_active_summary.serializer.account_active_summary_seriazlier import \
    AccountActiveSummarySerializer


class AccountActiveSummaryListView(APIView):
    renderer_classes = [
        CamelCaseJSONRenderer,
        BrowsableAPIRenderer,
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = AccountActiveSummaryService()

    def get(self, request):
        this_month = date_utils.get_first_day_of_month(datetime.date.today())
        # 過去12ヶ月
        summaries = self.service.list_monthly_summary(
            account=request.user.account,
            month_from=this_month - relativedelta(months=11),
            month_to=this_month,
        )

        response = AccountActiveSummarySerializer(summaries, many=True)
        return Response(data=response.data)
