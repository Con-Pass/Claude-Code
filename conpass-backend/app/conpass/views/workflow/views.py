import traceback
from logging import getLogger

from django.db import DatabaseError
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response

from conpass.models import WorkflowTaskMaster, Workflow, WorkflowStep, WorkflowTask, WorkflowTaskUser, User, \
    WorkflowStepComment, Contract
from conpass.models.constants import Statusable
from conpass.services.paginate.paginate import StandardResultsSetPagination
from conpass.services.workflow.workflow_service import WorkflowService
from conpass.views.workflow.serializer.workflow_serializer import WorkflowTaskMasterResponseBodySerializer, \
    WorkflowEditRequestBodySerializer, WorkflowListResponseSerializer, \
    WorkflowAllDataResponseBodySerializer, \
    WorkflowAllDataStepResponseBodySerializer, WorkflowAddCommentRequestBodySerializer, \
    WorkflowFinishTaskUserRequestBodySerializer, WorkflowFinishTaskUserResponseBodySerializer, \
    WorkflowRejectRequestBodySerializer, WorkflowNotificationListResponseBodySerializer, \
    WorkflowDeleteRequestBodySerializer, WorkflowCloneRequestBodySerializer, WorkflowStartRequestBodySerializer, \
    WorkflowsBodySerializer
import datetime
from django.utils.timezone import make_aware

logger = getLogger(__name__)


class WorkflowTaskMasterListView(APIView):

    def get(self, request):
        workflow_task_master = list(
            WorkflowTaskMaster.objects.filter(status=WorkflowTaskMaster.Status.ENABLE.value).all())

        res_serializer = WorkflowTaskMasterResponseBodySerializer(workflow_task_master)
        return Response(data=res_serializer.data)


class SortWorkflowListView(generics.ListAPIView):
    serializer_class = WorkflowListResponseSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        検索処理追加のためオーバーライド
        """
        # query
        request = self.request
        account_id = request.user.account_id

        wheres = {}
        # ログインユーザがシステム管理者の場合はアカウント縛りをしない
        if request.user.type != User.Type.ADMIN.value:
            wheres['account_id'] = account_id

        excludes = {
            'status': Workflow.Status.DISABLE.value,
        }
        # 連絡先ユーザも参照できる
        if request.user.type == User.Type.CLIENT.value:
            wheres['account_id'] = request.user.client.provider_account_id
            wheres['client_id'] = request.user.client.id

        # 絞り込み
        if workflow_id := request.query_params.get('id'):
            wheres['id'] = workflow_id
        workflowtype = request.query_params.get('workflowType')
        if workflowtype and workflowtype != '0':
            if workflowtype == str(Workflow.Type.SYSTEM_TEMPLATE.value):
                wheres['type__in'] = [Workflow.Type.TEMPLATE.value, Workflow.Type.SYSTEM_TEMPLATE.value]
            else:
                wheres['type'] = int(workflowtype)
        if names := request.query_params.get('name'):
            wheres['name__icontains'] = names
        if memo := request.query_params.get('memo'):
            wheres['memo__icontains'] = memo
        if contract_id := request.query_params.get('contractId'):
            wheres['contract_id'] = contract_id
        if status := request.query_params.get('status'):
            wheres['status'] = status
        current_step_id = request.query_params.getlist('currentStepIds[]')
        liststate = request.query_params.get('listState')
        if liststate is None:
            pass
        else:
            wheres['current_step_id__in'] = current_step_id
        step_id_status = request.query_params.get('stepIdStatus')
        if step_id_status == "true":
            wheres['current_step_id'] = 0

        # リクエストから 'createdBy' パラメータを取得
        created_by_name = request.query_params.get('createdBy')

        if created_by_name:
            wheres_user = {
                'account_id': account_id,
                'type': User.Type.ACCOUNT.value,
                'is_bpo': False,
                'username__icontains': created_by_name
            }
            # usernameがcreated_by_nameに部分一致するUserオブジェクトを検索
            matching_users = User.objects.filter(**wheres_user)
            created_by_id = [user.id for user in matching_users]
            # 結果のIDリストをクエリに使用
            wheres['created_by_id__in'] = created_by_id

        # 申請日のフィルタリング
        search_created_date_from = request.query_params.get('CreateDateFrom')
        search_created_date_to = request.query_params.get('CreateDateTo')
        if search_created_date_from:
            start_date = timezone.datetime.strptime(search_created_date_from, '%Y-%m-%d')
            start_date = timezone.make_aware(datetime.datetime.combine(start_date, datetime.time.min))
            wheres['created_at__gte'] = start_date
        if search_created_date_to:
            end_date = timezone.datetime.strptime(search_created_date_to, '%Y-%m-%d')
            end_date = timezone.make_aware(datetime.datetime.combine(end_date, datetime.time.max))
            wheres['created_at__lte'] = end_date

        # 更新日のフィルタリング
        search_update_date_from = request.query_params.get('UpdateDateFrom')
        search_update_date_to = request.query_params.get('UpdateDateTo')
        if search_update_date_from:
            start_date = timezone.datetime.strptime(search_update_date_from, '%Y-%m-%d')
            start_date = timezone.make_aware(datetime.datetime.combine(start_date, datetime.time.min))
            wheres['updated_at__gte'] = start_date
        if search_update_date_to:
            end_date = timezone.datetime.strptime(search_update_date_to, '%Y-%m-%d')
            end_date = timezone.make_aware(datetime.datetime.combine(end_date, datetime.time.max))
            wheres['updated_at__lte'] = end_date
        standard_query = Q(**wheres)
        # 大本のシステムデフォルトのテンプレートも表示対象（アカウントがnull）
        if workflowtype != str(Workflow.Type.WORKFLOW.value):
            system_wheres = {
                'account': None,
                'type': Workflow.Type.SYSTEM_TEMPLATE.value
            }
            system_query = Q(**system_wheres)
            filters = standard_query | system_query
        else:
            filters = standard_query
        workflow_list = list(Workflow.objects.exclude(**excludes).filter(filters)
                             .order_by('-created_at', '-type', 'account', '-id').all())

        queryset = workflow_list
        return queryset


class WorkflowEditView(APIView):

    def post(self, request):
        """
        ワークフロー一式を更新する
        """
        params = request.data
        req_serializer = WorkflowEditRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        request_data = req_serializer.data

        workflow_service = WorkflowService()
        try:
            workflow_id = workflow_service.edit_whole_workflow(request_data, self.request.user)
        except ValueError as e:
            return Response(e, status=status.HTTP_400_BAD_REQUEST)
        except Workflow.DoesNotExist:
            return Response({"msg": ["ワークフローが見つかりません"]}, status=status.HTTP_400_BAD_REQUEST)
        except WorkflowStep.DoesNotExist:
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        except WorkflowTask.DoesNotExist:
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        except WorkflowTaskUser.DoesNotExist:
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response(workflow_id, status.HTTP_200_OK)


class WorkflowStepDeleteView(APIView):

    def get(self, request):
        """
        ワークフローの特定のステップを無効にする
        前後を紐付け直す
        """
        pass


class WorkflowDataListView(APIView):
    def get(self, request):
        user = self.request.user

        workflow_service = WorkflowService()
        param = workflow_service.create_params_from_querystrings(request.query_params, user)
        result_raw = workflow_service.get_workflows(param)

        # フロントの形に合わせて整形する
        res_serializer = WorkflowsBodySerializer(result_raw)
        return Response(data=res_serializer.data)


class WorkflowAllDataView(APIView):
    def get(self, request):
        user = self.request.user

        workflow_service = WorkflowService()
        param = workflow_service.create_params_from_querystrings(request.query_params, user)
        result_raw = workflow_service.get_workflow_all_data(param)

        # フロントの形に合わせて整形する
        res_serializer = WorkflowAllDataResponseBodySerializer(result_raw)
        return Response(data=res_serializer.data)


class WorkflowStepDataView(APIView):
    def get(self, request):
        id = request.GET.get('id')

        workflow_service = WorkflowService()
        result_raw = workflow_service.get_workflow_step_data(id)

        # フロントの形に合わせて整形する
        res_serializer = WorkflowAllDataStepResponseBodySerializer(result_raw)
        return Response(data=res_serializer.data)


class WorkflowCloneDataView(APIView):
    def post(self, request):
        """
        ワークフローテンプレートを複製して、実際に使うワークフローを用意する
        ワークフローテンプレートからワークフローテンプレートも可
        """
        params = request.data.get('params')
        req_serializer = WorkflowCloneRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        template = req_serializer.data.get('template')
        name = req_serializer.data.get('name')
        clone_type = req_serializer.data.get('cloneType')
        renewal_contract_id = req_serializer.data.get('renewalContractId')

        workflow_service = WorkflowService()
        try:
            clone_id = workflow_service.clone_workflow(template, name, clone_type, renewal_contract_id, self.request.user)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response("エラーが発生しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(data=clone_id)


class WorkflowStartView(APIView):
    def get(self, request):
        """
        ワークフローを開始する
        current_step_id が入る
        最初のステップの開始日が入る
        """
        req_serializer = WorkflowStartRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        workflow_id = req_serializer.data.get('id')
        directory_id = req_serializer.data.get('directoryId')

        workflow_service = WorkflowService()
        try:
            start_id = workflow_service.start_workflow(workflow_id, directory_id, self.request.user)
        except DatabaseError as e:
            return Response(e, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response(e, status=status.HTTP_400_BAD_REQUEST)

        if start_id > 0:
            return Response("OK", status=status.HTTP_200_OK)
        else:
            return Response("ワークフローの開始に失敗しました", status=status.HTTP_400_BAD_REQUEST)


class WorkflowAddStepCommentView(APIView):

    def post(self, request):
        """
        ステップにコメントを残す
        ステップの遷移orリジェクト時となる
        基本的に更新はなくて、どんどん積んでゆく形です
        """
        params = request.data
        req_serializer = WorkflowAddCommentRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        request_data = req_serializer.data

        login_user = request.user
        now = make_aware(datetime.datetime.now())

        workflow_service = WorkflowService()
        try:
            comment_id = workflow_service.add_step_comment(request_data.get('stepId'), login_user, request_data.get('comment'), now)
        except WorkflowStep.DoesNotExist:
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response(str(comment_id), status=status.HTTP_200_OK)


class WorkflowFinishTaskUserView(APIView):

    def post(self, request):
        """
        ワークフローのタスクを特定のユーザあるいはグループが完了させた
        ただし、タスク自体が完了になるかは別（タスクの完了条件による）
        """
        params = request.data
        req_serializer = WorkflowFinishTaskUserRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        request_data = req_serializer.data

        login_user = request.user

        workflow_service = WorkflowService()
        result = workflow_service.finish_workflow_task(request_data, login_user, None)

        res_serializer = WorkflowFinishTaskUserResponseBodySerializer(result)
        return Response(data=res_serializer.data)


class WorkflowRejectStepView(APIView):
    def post(self, request):
        """
        ワークフローのステップがリジェクトされた
        """
        params = request.data
        req_serializer = WorkflowRejectRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        request_data = req_serializer.data

        login_user = request.user

        workflow_service = WorkflowService()
        # 戻る位置までのタスクをすべて未完了に戻す
        workflow_service.reject_workflow_step(request_data, login_user)

        return Response(status=status.HTTP_200_OK)


class WorkflowNotificationListView(APIView):
    def get(self, request):
        """
        ダッシュボードで表示する通知項目リスト
        ページャは考慮しなくて良い
        """
        login_user = request.user

        workflow_service = WorkflowService()
        my_task_users = workflow_service.get_workflow_mytask_list(login_user)
        results = []
        for task_user in my_task_users:
            client = task_user.task.step.workflow.client
            contract = task_user.task.step.workflow.contract
            result = {
                'workflowId': task_user.task.step.workflow.id,
                'stepId': task_user.task.step.id,
                'stepStart': task_user.task.step.start_date,
                'stepLimit': task_user.task.step.expire_day,
                'taskId': task_user.task.id,
                'taskName': task_user.task.name,
                'taskType': task_user.task.task.type if task_user.task.task else 0,
                'clientId': client.id if client else None,
                'clientName': client.name if client else None,
                'contractId': contract.id if contract else None,
                'contractName': contract.name if contract else None,
            }
            results.append(result)
        res_serializer = WorkflowNotificationListResponseBodySerializer(results)
        return Response(data=res_serializer.data)


class WorkflowDeleteView(APIView):
    def post(self, request):
        """
        ワークフローを削除
        テンプレートかワークフローかはパラメータで指定します
        """
        params = request.data
        req_serializer = WorkflowDeleteRequestBodySerializer(data=params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        request_data = req_serializer.data

        login_user = request.user
        now = make_aware(datetime.datetime.now())

        wheres = {
            'id__in': request_data.get('ids'),
        }
        excludes = {
            'status': Workflow.Status.DISABLE.value,
        }
        if login_user.type != User.Type.ADMIN.value:
            wheres['account'] = login_user.account
        if request_data.get('workflowType') == Workflow.Type.SYSTEM_TEMPLATE.value:
            wheres['type__in'] = [Workflow.Type.TEMPLATE.value, Workflow.Type.SYSTEM_TEMPLATE.value]
        else:
            wheres['type'] = request_data.get('workflowType')

        try:
            workflows = list(Workflow.objects.exclude(**excludes).filter(**wheres).all())
        except Workflow.DoesNotExist as e:
            logger.info(e)
            return Response("パラメータが不正です", status=status.HTTP_400_BAD_REQUEST)

        try:
            delete_list = []
            for workflow in workflows:
                workflow.status = Workflow.Status.DISABLE.value
                workflow.updated_at = now
                workflow.updated_by = login_user
                delete_list.append(workflow)
            Workflow.objects.bulk_update(delete_list, fields=['status', 'updated_at', 'updated_by'])
            if request_data.get('workflowType') == Workflow.Type.WORKFLOW.value:

                def f(w):
                    w.status = Statusable.Status.DISABLE.value
                    w.updated_at = now
                    w.updated_by = login_user
                    return w

                target_wf_id = list(map(lambda w: w.id, delete_list))
                ws_list = list(WorkflowStep.objects.filter(**{'workflow_id__in': target_wf_id}).all())
                ws_list = list(map(f, ws_list))
                WorkflowStep.objects.bulk_update(ws_list, fields=['status', 'updated_at', 'updated_by'])

                target_ws_id = list(map(lambda ws: ws.id, ws_list))
                wt_list = list(WorkflowTask.objects.filter(**{'step_id__in': target_ws_id}).all())
                wt_list = list(map(f, wt_list))
                WorkflowTask.objects.bulk_update(wt_list, fields=['status', 'updated_at', 'updated_by'])

                wsc_list = list(WorkflowStepComment.objects.filter(**{'step_id__in': target_ws_id}).all())
                wsc_list = list(map(f, wsc_list))
                WorkflowStepComment.objects.bulk_update(wsc_list, fields=['status', 'updated_at', 'updated_by'])

                target_wt_id = list(map(lambda wt: wt.id, wt_list))
                wtu_list = list(WorkflowTaskUser.objects.filter(**{'task_id__in': target_wt_id}).all())
                wtu_list = list(map(f, wtu_list))
                WorkflowTaskUser.objects.bulk_update(wtu_list, fields=['status', 'updated_at', 'updated_by'])

        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response("エラーが発生しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)
