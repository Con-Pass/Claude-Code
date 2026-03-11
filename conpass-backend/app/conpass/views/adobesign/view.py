import io
from logging import getLogger
from django.conf import settings
from django.db.models import Q
from django.db.utils import DatabaseError
from django.utils.timezone import make_aware
from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from conpass.models import Account, AdobeSign, AdobeSetting, Contract, ContractBody, File, WorkflowStep, User, \
    WorkflowStepComment, AdobeSignApprovalUser, WorkflowTaskUser, WorkflowTask, Workflow, WorkflowTaskMaster
from conpass.services.adobesign.adobesign_service import AdobeSignService
from conpass.services.gcp.cloud_storage import GoogleCloudStorage, GCSBucketName
from conpass.services.workflow.workflow_service import WorkflowService
from conpass.views.adobesign.serializer.adobe_sign_serializer import AdobeSignRequestBodySerializer, \
    AdobeSignTransientDocumentsFileRequestSerializer, AdobeSignCertificationRequestSerializer

import datetime
import json
import requests
import traceback
import urllib.parse
from google.cloud import storage
from rest_framework.permissions import AllowAny

logger = getLogger(__name__)

ADOBESIGN_WEB_CERTIFICATION_PATH = 'public/oauth/v2'
ADOBESIGN_API_CERTICICATION_AUTH_PATH = 'oauth/v2/token'
ADOBESIGN_API_WEBHOOK_PATH = 'api/rest/v6/webhooks'


class AdobeSignConfirmView(APIView):

    def get(self, request):
        user = self.request.user
        if AdobeSetting.objects.filter(account_id=user.account_id, status=AdobeSetting.Status.ENABLE.value).exists():
            adobe_setting = AdobeSetting.objects.filter(account_id=user.account_id,
                                                        status=AdobeSetting.Status.ENABLE.value).get()
        else:
            adobe_setting = AdobeSetting()
        access_token = adobe_setting.access_token

        return Response(data=access_token, status=status.HTTP_200_OK)


class AdobeSignCertificationView(APIView):

    def get(self, request):
        req_serializer = AdobeSignCertificationRequestSerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        application_id = req_serializer.data.get('applicationId')
        client_secret = req_serializer.data.get('clientSecret')
        user = self.request.user
        now = make_aware(datetime.datetime.now())

        if AdobeSetting.objects.filter(account_id=user.account_id,
                                       status=AdobeSetting.Status.ENABLE.value).exists():
            adobe_setting = AdobeSetting.objects.filter(account_id=user.account_id,
                                                        status=AdobeSetting.Status.ENABLE.value).get()
        else:
            adobe_setting = AdobeSetting()
            adobe_setting.account = user.account
            adobe_setting.status = AdobeSetting.Status.ENABLE.value
            adobe_setting.access_token = ""
            adobe_setting.refresh_token = ""
            adobe_setting.expires_in = 0
            adobe_setting.created_at = now
            adobe_setting.created_by = user

        adobe_setting.application_id = application_id
        adobe_setting.client_secret = client_secret
        adobe_setting.updated_at = now
        adobe_setting.updated_by = user
        adobe_setting.save()

        endpoint = settings.ADOBESIGN_WEB_ACCESS_POINT + ADOBESIGN_WEB_CERTIFICATION_PATH
        redirect = settings.ADOBESIGN_APPLICATION_REDIRECT
        params = {
            'redirect_uri': redirect,
            'response_type': 'code',
            'client_id': application_id,
            # scopeはadobesign管理画面のアプリOAuth設定で設定したものの範囲内となる。なるべく合わせる
            'scope': 'user_login agreement_read agreement_write agreement_send webhook_write webhook_read',
        }

        will_redirect = endpoint + '?' + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        return Response(data=will_redirect)


class AdobeSignCertificationAuthView(APIView):

    def get(self, request):
        req_serializer = AdobeSignRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = self.request.user

        try:
            adobe_setting = AdobeSetting.objects.filter(account_id=user.account_id,
                                                        status=AdobeSetting.Status.ENABLE.value).get()
        except AdobeSetting.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["API連携が完了しておりません"]}, status=status.HTTP_400_BAD_REQUEST)

        endpoint = settings.ADOBESIGN_API_ACCESS_POINT + ADOBESIGN_API_CERTICICATION_AUTH_PATH
        data = {
            'code': req_serializer.data.get('code'),
            'client_id': adobe_setting.application_id,
            'client_secret': adobe_setting.client_secret,
            'redirect_uri': settings.ADOBESIGN_APPLICATION_REDIRECT,
            'grant_type': 'authorization_code'
        }

        # URLをエンコード
        params = urllib.parse.urlencode(data)
        # headerでコンテンツタイプを指定
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        r = requests.post(url=endpoint, data=params, headers=headers)
        context = json.loads(r.text)

        try:
            adobe_setting.account_id = user.account_id
            adobe_setting.access_token = context['access_token']
            adobe_setting.refresh_token = context['refresh_token']
            adobe_setting.expires_in = context['expires_in']
            adobe_setting.updated_at = make_aware(datetime.datetime.now())
            adobe_setting.updated_by = user
            adobe_setting.save()

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status.HTTP_200_OK)


class AdobeSignGetBaseURIView(APIView):

    def get(self, request):
        user = self.request.user
        try:
            adobe_setting = AdobeSetting.objects.filter(account_id=user.account_id,
                                                        status=AdobeSetting.Status.ENABLE.value).get()
        except AdobeSetting.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["API連携が完了しておりません"]}, status=status.HTTP_400_BAD_REQUEST)

        adobesign_service = AdobeSignService()
        r = adobesign_service.get_base_uris(adobe_setting, user)

        return Response(r)


class AdobeSignCreateWebhookView(APIView):

    def get(self, request):
        user = self.request.user
        try:
            adobe_setting = AdobeSetting.objects.filter(account_id=user.account_id,
                                                        status=AdobeSetting.Status.ENABLE.value).get()
        except AdobeSetting.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["API連携が完了しておりません"]}, status=status.HTTP_400_BAD_REQUEST)

        access_token = adobe_setting.access_token
        endpoint = settings.ADOBESIGN_API_ACCESS_POINT + ADOBESIGN_API_WEBHOOK_PATH

        # headerでコンテンツタイプを指定
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + access_token,
        }

        params = {
            'name': 'webhook',  # 登録済の場合は上書きできないので、adobesignの管理画面側で無効にする必要がある
            'scope': 'ACCOUNT',
            'state': 'ACTIVE',
            'webhookSubscriptionEvents': ['AGREEMENT_ALL'],
            'webhookUrlInfo': {
                'url': settings.ADOBESIGN_WEBHOOK_URL},
        }

        # webhookの作成
        r = requests.post(url=endpoint, headers=headers, data=json.dumps(params))
        context = json.loads(r.text)

        return Response(data=context["id"], status=status.HTTP_200_OK)


class AdobeSignWebhookView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """
        初回の疎通確認
        """
        # webhook用のclient id が払い出される
        client_id = request.META.get("HTTP_X_ADOBESIGN_CLIENTID")
        logger.info(client_id)
        return Response(headers={'X-AdobeSign-ClientId': client_id},
                        status=status.HTTP_201_CREATED)

    def post(self, request):

        # webhookの検知内容
        # webhook 時は request.user は取れないので注意
        datas = json.loads(request.body)
        event = datas['event']
        client_id = request.META.get("HTTP_X_ADOBESIGN_CLIENTID")
        logger.info("webhook:" + event + ", client id:" + client_id)
        logger.info(datas)
        if event == 'AGREEMENT_CREATED':
            # 契約が作成されたとき
            pass

        agreement = datas['agreement']
        acting_user_email = datas['actingUserEmail']
        participant_user_email = datas['participantUserEmail']
        if event == 'AGREEMENT_ACTION_COMPLETED':
            # 契約書に署名したとき
            self.work_flow_add_step_comment(agreement, acting_user_email)
        elif event == 'AGREEMENT_ACTION_DELEGATED':
            # 契約が参加者によって委任されたとき
            self._set_delegate(agreement, acting_user_email, participant_user_email)
        elif event == 'AGREEMENT_WORKFLOW_COMPLETED':
            # 全員の確認が終わったので、署名済のpdfをダウンロードする
            self._download_signed_pdf(agreement)
        elif event == 'AGREEMENT_REJECTED':
            # adobesign側で承認が辞退された
            # 承認依頼メールの「確認して承認」を開き、左上のオプションから「承認を辞退する」
            # adobesign側のstatusは "CANCELLED"
            self._cancel_agreement(agreement, acting_user_email)

        self._create_webhook_log(datas)

        return Response(headers={'X-AdobeSign-ClientId': client_id},
                        status=status.HTTP_201_CREATED)

    def _create_webhook_log(self, datas: dict):

        # webhookログはFileDBでは管理しません
        event = datas['event']
        agreement = datas['agreement']

        try:
            adobe_sign = AdobeSign.objects.filter(agreement_id=agreement['id'],
                                                  status=AdobeSign.Status.ENABLE.value).get()
        except AdobeSign.DoesNotExist:
            return

        account_id = adobe_sign.workflow.account_id
        user_id = adobe_sign.workflow.created_by_id

        now = datetime.datetime.now().replace(tzinfo=None).strftime('%Y%m%d%H%M%S')
        filename = "{}_{}.json"
        filename = filename.format(event, now)

        cloud_storage = GoogleCloudStorage()
        cloud_storage.set_user_id(user_id)
        client, bucket = cloud_storage.get_cloudstorage(GCSBucketName.API)
        gcs_path = self._make_gcs_webhook_fileinfo(account_id, adobe_sign.workflow_id, adobe_sign.agreement_id,
                                                   filename)
        gcs_blob = bucket.blob(gcs_path)  # GCS側
        encode_json_data = json.dumps(datas)
        gcs_blob.upload_from_string(encode_json_data)  # local側

        cloud_storage.set_user_id(0)

    def _make_gcs_webhook_fileinfo(self, account_id, workflow_id, agreement_id, filename) -> str:
        """
        webhookからgscにアップするURLを作る
        webhook/{顧客ID}/{ワークフローID}/{adobesignのagreementID}/{webhookイベント名}_{日時}.json
        """
        url = settings.GCS_FILE_PREFIX + 'webhook/{}/{}/{}/{}'
        file_url = url.format(account_id, workflow_id, agreement_id, filename)
        return file_url

    def work_flow_add_step_comment(self, agreement, acting_user_email):
        """
        ステップにコメントを残す
        ステップの遷移orリジェクト時となる
        基本的に更新はなくて、どんどん積んでゆく形です
        """

        adobe_sign = AdobeSign.objects.filter(agreement_id=agreement['id'], status=AdobeSign.Status.ENABLE.value).get()
        adobe_sign_approval_user = AdobeSignApprovalUser.objects.filter(adobesign=adobe_sign,
                                                                        approval_mail_address=acting_user_email,
                                                                        status=AdobeSignApprovalUser.Status.ENABLE.value).get()
        user = adobe_sign_approval_user.user

        workflow = adobe_sign.workflow
        now = make_aware(datetime.datetime.now())

        workflow_service = WorkflowService()
        try:
            workflow_service.add_step_comment(workflow.current_step_id, user, 'AdobeSignで対応が完了しました', now)
        except WorkflowStep.DoesNotExist as e:
            raise e

        wheres = {
            'step_id': workflow.current_step_id,
            'status': WorkflowTask.Status.ENABLE.value,
            'task__type__in': [WorkflowTaskMaster.Type.SIGN.value, WorkflowTaskMaster.Type.SIGN_URL.value],
        }
        if WorkflowTask.objects.filter(**wheres).exists():
            workflow_task = WorkflowTask.objects.filter(**wheres).get()
            # このタスクの担当者にuserが居るかどうか探す
            taskuser_where = {
                'task_id': workflow_task.id,
                'status': WorkflowTaskUser.Status.ENABLE.value,
            }
            taskuser_ids = []
            # userに含まれるかどうか
            in_user = WorkflowTaskUser.objects.filter(Q(**taskuser_where), Q(user=user))
            if in_user.exists():
                taskuser_ids.append(in_user.get().id)
            # group に含まれるかどうか
            task_groups = list(WorkflowTaskUser.objects.select_related('group').filter(Q(**taskuser_where),
                                                                                       Q(group__isnull=False)).all())
            for task_group in task_groups:
                if task_group.group.objects.filter(user__in=user).exists():
                    taskuser_ids.append(task_group.get().id)

            for taskuser_id in taskuser_ids:
                params = {
                    'taskId': workflow_task.id,
                    'taskUserId': taskuser_id,
                }
                try:
                    workflow_service.finish_workflow_task(params, user, now)
                except Exception as e:
                    raise e

    def _set_delegate(self, agreement, acting_user_email, participant_user_email):
        adobe_sign = AdobeSign.objects.filter(agreement_id=agreement['id'], status=AdobeSign.Status.ENABLE.value).get()
        adobe_sign_approval_user = AdobeSignApprovalUser.objects.filter(adobesign=adobe_sign,
                                                                        approval_mail_address=acting_user_email,
                                                                        status=AdobeSignApprovalUser.Status.ENABLE.value).get()
        adobe_sign_approval_user.approval_mail_address = participant_user_email
        adobe_sign_approval_user.status = AdobeSignApprovalUser.Status.ENABLE.value
        adobe_sign_approval_user.updated_at = make_aware(datetime.datetime.now())
        adobe_sign_approval_user.updated_by = adobe_sign_approval_user.user
        adobe_sign_approval_user.save()

    def _download_signed_pdf(self, agreement: dict):
        """
        電子署名済のpdfをadobesignからダウンロードしてGCSに保存し、登録する
        """
        adobe_sign = AdobeSign.objects.filter(agreement_id=agreement['id'], status=AdobeSign.Status.ENABLE.value).get()
        try:
            adobe_setting = AdobeSetting.objects.filter(account_id=adobe_sign.workflow.account_id,
                                                        status=AdobeSetting.Status.ENABLE.value).get()
        except AdobeSetting.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["API連携が完了しておりません"]}, status=status.HTTP_400_BAD_REQUEST)

        user = adobe_sign.workflow.created_by

        adobesign_service = AdobeSignService()
        r = adobesign_service.combined_document(agreement, adobe_setting, user)
        if r.status_code == status.HTTP_200_OK:
            cloud_storage = GoogleCloudStorage()
            try:
                pdf_name = agreement['name'] if agreement['name'].casefold().endswith('.pdf') else agreement['name'] + '.pdf'
                cloud_storage.set_user_id(user.id)
                client, bucket = cloud_storage.get_cloudstorage(GCSBucketName.FILE)
                data_type = File.Type.ETC.value  # 一旦関連としておきます
                file = cloud_storage.prepare_file_record(0, pdf_name, data_type)
                _, gcs_path = cloud_storage.get_gcs_fileinfo(file)
                gcs_blob = bucket.blob(gcs_path)  # GCS側
                file_obj = io.BytesIO()
                file_obj.write(r.content)
                file_obj.seek(0)
                gcs_blob.upload_from_file(file_obj)
                cloud_storage.set_file_info(file=file, filename=pdf_name, url=gcs_path, datatype=data_type,
                                            description="電子署名済pdf", size=gcs_blob.size)
                # 契約書を電子署名済にして電子署名済ファイルを紐づける
                contract = adobe_sign.contract
                contract.status = Contract.Status.SIGNED.value
                contract.save()
                contract.file.add(file)
            except Exception as e:
                logger.error(f"{e}: {traceback.format_exc()}")
                raise e
            finally:
                cloud_storage.set_user_id(0)  # クリアしておく

    def _cancel_agreement(self, agreement: dict, acting_user_email: str):
        adobe_sign = AdobeSign.objects.filter(agreement_id=agreement['id'], status=AdobeSign.Status.ENABLE.value).get()
        adobe_sign_approval_user = AdobeSignApprovalUser.objects.filter(adobesign=adobe_sign,
                                                                        approval_mail_address=acting_user_email,
                                                                        status=AdobeSignApprovalUser.Status.ENABLE.value).get()
        user = adobe_sign_approval_user.user

        # そのタスクのステップをリジェクトする
        workflow = adobe_sign.workflow
        step_id = workflow.current_step_id
        workflow_step = WorkflowStep.objects.filter(pk=step_id, status=WorkflowStep.Status.ENABLE.value).get()

        workflow_service = WorkflowService()
        now = make_aware(datetime.datetime.now())

        try:
            workflow_service.add_step_comment(step_id, user, 'AdobeSignで承認が辞退されました', now)
        except WorkflowStep.DoesNotExist as e:
            raise e

        params = {
            'stepId': step_id,  # 現在のステップ
            'rejectCount': workflow_step.reject_step_count,  # 戻すカウント数
        }
        try:
            workflow_service.reject_workflow_step(params, user)
        except Exception as e:
            raise e

        # 無効にする
        adobe_sign.status = AdobeSign.Status.DISABLE.value
        adobe_sign.save()
