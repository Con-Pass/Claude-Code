# Create your views here.
from logging import getLogger

from celery.result import AsyncResult
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.models import User
from conpass.tasks import add
from conpass.views.sys.common import SysAPIView

logger = getLogger(__name__)


class IndexView(APIView):
    permission_classes = []

    def get(self, request):
        context = {'foo': 'bar'}
        logger.info('hello', extra={'context': context})
        logger.info(len(User.objects.all()))
        return Response(data={"hello": 300})


class DelayView(APIView):
    def get(self, request):
        task_id: AsyncResult = add.delay(4, 5)
        return Response(data={
            'task_id': task_id.task_id
        })


# storeで覚えるユーザ情報
class UserView(APIView):
    def get(self, request):
        user: User = request.user
        return Response(data={
            'id': user.pk,
            'username': user.username,
            'email': user.email,
            'type': user.type,
            'isBpo': user.is_bpo,
            'accountName': user.account.name,
            'accountPlan': user.account.plan,
            'accountMfaStatus': user.account.mfa_status,
            'accountIpaddressStatus': user.account.ipaddress_status,
            'isBpoAdmin': user.is_bpo_admin,
            'wfBpoTaskDelegatedStampStatus': user.account.wf_bpo_task_delegated_stamp_status,
            'wfBpoTaskDelegatedReceiptStatus': user.account.wf_bpo_task_delegated_receipt_status,
            'orgId': user.account.org_id,
            'ssoStatus': user.account.sso_status,
            'permissionCategoryName': user.permission_category.name if user.permission_category else '',
        })


class SysUserView(SysAPIView):
    def get(self, request):
        user: User = request.user
        return Response(data={
            'id': user.pk,
            'username': user.username,
            'email': user.email,
            'type': user.type,
            'accountPlan': user.account.plan if user.account else 0,
        })


class Dashboard(APIView):
    def get(self, request):
        return Response({"data": "helloworld"})
