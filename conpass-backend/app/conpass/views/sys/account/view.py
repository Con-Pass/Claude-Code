import traceback
import csv
import uuid
import pyotp
import random
import string
from logging import getLogger

from django.http import HttpResponse
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from conpass.services.user.user_service import UserService
from conpass.services.ipaddress.ipaddress_service import IpAddressService
from conpass.views.sys.account.serializer.account_serializer import AccountRequestBodySerializer, \
    AccountResponseBodySerializer
from conpass.views.sys.account.serializer.account_detail_serializer import AccountDetailResponseBodySerializer
from conpass.views.sys.account.serializer.account_edit_serializer import AccountEditResponseBodySerializer, \
    AccountEditRequestBodySerializer
from conpass.views.sys.account.serializer.account_create_serializer import AccountCreateRequestBodySerializer
from conpass.models import Account, Corporate, User, PermissionTarget, IpAddress
import datetime
from django.utils.timezone import make_aware
from django.contrib.auth.hashers import make_password
from django.db.utils import DatabaseError
from conpass.models.constants import Statusable

from conpass.views.sys.common import SysAPIView

logger = getLogger(__name__)


class SysAccountListView(SysAPIView):

    def get(self, request):
        # request
        req_serializer = AccountRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wheres = {}
        if req_serializer.data.get('name'):
            wheres['name__contains'] = req_serializer.data.get('name')
        if req_serializer.data.get('status'):
            wheres['status'] = req_serializer.data.get('status')
        if req_serializer.data.get('plan'):
            wheres['plan'] = req_serializer.data.get('plan')

        # query
        account_list = list(Account.objects.exclude(**{'status': Account.Status.DISABLE.value}).filter(**wheres).all())

        # response
        res_serializer = AccountResponseBodySerializer(account_list)
        return Response(data=res_serializer.data)


class SysAccountListDownloadView(SysAPIView):

    def get(self, request):
        # query
        account_list = list(Account.objects.exclude(**{'status': Account.Status.DISABLE.value}).all())

        t_delta = datetime.timedelta(hours=9)
        jst = datetime.timezone(t_delta, 'JST')
        now = datetime.datetime.now(jst)
        file_name = 'conpass_account_{file_date}'.format(file_date=now.strftime('%Y%m%d%H%M%S'))
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{file_name}.csv"'.format(file_name=file_name)
        writer = csv.writer(response, quotechar='"')

        # ここからcsvの内容を編集コード
        writer.writerow(['名前', 'プラン', '開始日', '解約日', 'ステータス', 'ConPass BPO 代理押印', 'ConPass BPO 代理受取', '組織ID', 'SSO契約状態'])
        for account in account_list:
            plan_name = Account.Plan(account.plan).name
            status_name = Account.Status(account.status).name
            wf_delegated_stamp_status_name = Account.WfBpoTaskDelegatedStampStatus(account.wf_bpo_task_delegated_stamp_status).name
            wf_delegated_receipt_status_name = Account.WfBpoTaskDelegatedReceiptStatus(account.wf_bpo_task_delegated_receipt_status)
            status_name = Account.Status(account.status).name
            sso_status_name = Account.SsoStatus(account.sso_status).name
            writer.writerow([
                account.name,
                Account.PlanDisplayName[plan_name].value,
                account.start_date,
                account.cancel_date,
                account.StatusDisplayName[status_name].value,
                Account.WfBpoTaskDelegatedStampStatusDisplayName[wf_delegated_stamp_status_name].value,
                Account.WfBpoTaskDelegatedStampStatusDisplayName[wf_delegated_receipt_status_name].value,
                account.org_id,
                Account.SsoStatusDisplayName[sso_status_name].value,
            ])

        return response


class SysAccountDeleteView(SysAPIView):
    def post(self, request):
        params = request.data
        result_list = []
        datetime_now = make_aware(datetime.datetime.now())
        user_service = UserService()
        for delete_id in list(params['ids']):
            try:
                delete_account = Account.objects.get(pk=delete_id)
                delete_account.status = Account.Status.DISABLE.value
                delete_account.updated_by_id = self.request.user.id
                delete_account.updated_at = datetime_now
                delete_account.save()
                # accountに紐づくユーザも消込をする
                delete_users = list(User.objects.filter(account=delete_account).all())
                user_service.bulk_delete_user_data(delete_users, self.request.user, datetime_now)

                result_list.append(delete_id)
            except Account.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data=result_list)


class SysAccountDetailView(SysAPIView):
    def get(self, request):
        account_id = request.query_params.get('id')
        try:
            account = Account.objects.get(pk=account_id)
        except Account.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        res_serializer = AccountDetailResponseBodySerializer(account)
        return Response(data=res_serializer.data)


class SysAccountEditView(SysAPIView):
    def get(self, request):
        account_id = request.query_params.get('id')
        try:
            account = Account.objects.get(pk=account_id)
        except Account.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        res_serializer = AccountEditResponseBodySerializer(account)
        return Response(data=res_serializer.data)

    def post(self, request):
        params = request.data
        req_serializer = AccountEditRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            account = Account.objects.get(pk=params.get('id'))

            account.name = req_serializer.data.get('name')
            account.status = req_serializer.data.get('status')
            account.plan = req_serializer.data.get('plan')
            account.mfa_status = req_serializer.data.get('mfaStatus')
            account.wf_bpo_task_delegated_stamp_status = req_serializer.data.get('wfBpoTaskDelegatedStampStatus')
            account.wf_bpo_task_delegated_receipt_status = req_serializer.data.get('wfBpoTaskDelegatedReceiptStatus')
            account.start_date = req_serializer.data.get('startDate')
            account.cancel_date = req_serializer.data.get('cancelDate')
            account.ipaddress_status = req_serializer.data.get('ipaddressStatus')
            account.updated_by_id = self.request.user.id
            account.updated_at = make_aware(datetime.datetime.now())
            account.sso_status = req_serializer.data.get('ssoStatus')
            account.chatbot_access = req_serializer.data.get('chatbotAccess')
            account.save()

        except Account.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status.HTTP_200_OK)


class SysAccountCreateView(SysAPIView):
    def post(self, request):
        params = request.data
        req_serializer = AccountCreateRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        login_user = self.request.user
        now = make_aware(datetime.datetime.now())
        # User.login_name重複チェック
        if User.objects.filter(login_name=req_serializer.data.get('loginName')).count() > 0:
            return Response({"msg": ["ログインIDが重複しています。"]}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            account = Account()
            try:
                account.name = req_serializer.data.get('name')
                account.status = req_serializer.data.get('status')
                account.plan = req_serializer.data.get('plan')
                account.mfa_status = req_serializer.data.get('mfaStatus')
                account.wf_bpo_task_delegated_stamp_status = req_serializer.data.get('wfBpoTaskDelegatedStampStatus')
                account.wf_bpo_task_delegated_receipt_status = req_serializer.data.get('wfBpoTaskDelegatedReceiptStatus')
                account.start_date = req_serializer.data.get('startDate')
                account.cancel_date = req_serializer.data.get('cancelDate')
                account.ipaddress_status = req_serializer.data.get('ipaddressStatus')
                account.created_by_id = login_user.id
                account.created_at = now
                account.updated_by_id = login_user.id
                account.updated_at = now
                account.org_id = self._create_org_id()
                account.sso_status = req_serializer.data.get('ssoStatus')
                account.chatbot_access = req_serializer.data.get('chatbotAccess')
                account.save()
            except DatabaseError as e:
                logger.error(f"{e}: {traceback.format_exc()}")
                return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            corporate = Corporate()
            if req_serializer.data.get('corporateName') and \
                    req_serializer.data.get('address') and \
                    req_serializer.data.get('executiveName') and \
                    req_serializer.data.get('salesName') and \
                    req_serializer.data.get('url') and \
                    req_serializer.data.get('corporateTel'):
                try:
                    corporate.account_id = account.id
                    corporate.name = req_serializer.data.get('corporateName')
                    corporate.address = req_serializer.data.get('address')
                    corporate.executive_name = req_serializer.data.get('executiveName')
                    corporate.sales_name = req_serializer.data.get('salesName')
                    corporate.service = req_serializer.data.get('service')
                    corporate.url = req_serializer.data.get('url')
                    corporate.tel = req_serializer.data.get('corporateTel')
                    corporate.status = Corporate.Status.ENABLE.value
                    corporate.created_by_id = login_user.id
                    corporate.created_at = now
                    corporate.updated_by_id = login_user.id
                    corporate.updated_at = now
                    corporate.save()
                except DatabaseError as e:
                    logger.error(f"{e}: {traceback.format_exc()}")
                    return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 初期ユーザを作る
            params = {
                'account_id': account.id,
                'corporate_id': corporate.id if corporate else None,
                'login_name': req_serializer.data.get('loginName'),
                'username': req_serializer.data.get('userName'),
                'password': req_serializer.data.get('password'),
                'division': req_serializer.data.get('division'),
                'position': req_serializer.data.get('position'),
                'tel': req_serializer.data.get('userTel'),
                'memo': req_serializer.data.get('memo'),
                'mfa_status': req_serializer.data.get('userMfaStatus'),
                'email': req_serializer.data.get('loginName'),
                'is_bpo': False,
            }
            try:
                self._create_user(params, login_user, now)
            except DatabaseError:
                return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status.HTTP_200_OK)

    def _create_user(self, params: dict, login_user: User, now: datetime):
        try:
            user = User()
            user.account_id = params.get('account_id')
            if params.get('corporate_id'):
                user.corporate_id = params.get('corporate_id')
            user.type = User.Type.ACCOUNT.value
            user.is_bpo = params.get('is_bpo')
            user.login_name = params.get('login_name')
            user.username = params.get('username')
            user.password = make_password(params.get('password'))
            user.division = params.get('division')
            user.position = params.get('position')
            user.tel = params.get('tel')
            user.memo = params.get('memo')
            user.status = User.Status.ENABLE.value
            user.mfa_status = params.get('mfa_status')
            user.date_joined = now
            user.email = params.get('email')
            user.is_active = 1
            user.is_staff = 0
            user.is_superuser = 0
            user.created_by_id = login_user.id
            user.created_at = now
            user.updated_by_id = login_user.id
            user.updated_at = now
            user.otp_secret = pyotp.random_base32()
            user.save()

            # 最初に作るユーザは全権限を許可にする
            user_service = UserService()
            allow_targets = [target.value for target in PermissionTarget.Target]
            user_service.create_user_permissions(user, login_user, now, allow_targets, [])

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e

    # 半角英数6文字（小文字）
    def _create_org_id(self):
        characters = string.ascii_lowercase + string.digits
        unique_string = ''.join(random.choice(characters) for _ in range(6))
        wheres = {'org_id': unique_string}
        is_exist = Account.objects.filter(**wheres).exists()
        if is_exist:
            unique_string = self._create_org_id()
        return unique_string
