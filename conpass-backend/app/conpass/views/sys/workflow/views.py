import datetime
import traceback

from django.db.models import Q
from django.utils.timezone import make_aware

from conpass.models import Workflow, WorkflowStep, WorkflowTask, WorkflowTaskUser, User
from conpass.services.paginate.paginate import StandardResultsSetPagination
from conpass.services.workflow.workflow_service import WorkflowService
from conpass.views.sys.common import SysAPIView, SysListAPIView
from rest_framework.response import Response
from rest_framework import status, generics
from conpass.views.workflow.serializer.workflow_serializer import WorkflowEditRequestBodySerializer, \
    WorkflowCloneRequestBodySerializer, WorkflowsBodySerializer, WorkflowAllDataResponseBodySerializer, \
    WorkflowListResponseSerializer, WorkflowDeleteRequestBodySerializer
from logging import getLogger

logger = getLogger(__name__)


class SysWorkflowEditView(SysAPIView):

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
        except Workflow.DoesNotExist:
            return Response({"msg": ["ワークフローが見つかりません"]}, status=status.HTTP_400_BAD_REQUEST)
        except WorkflowStep.DoesNotExist:
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        except WorkflowTask.DoesNotExist:
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
        except WorkflowTaskUser.DoesNotExist:
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response(workflow_id, status.HTTP_200_OK)


class SysWorkflowCloneDataView(SysAPIView):

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
            clone_id = workflow_service.clone_workflow(template, name, clone_type, renewal_contract_id,
                                                       self.request.user)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response("エラーが発生しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(data=clone_id)


class SysWorkflowDataListView(SysAPIView):

    def get(self, request):
        """
        ワークフローのリスト
        stepやtaskなどの情報は持っていない
        """
        user = self.request.user

        workflow_service = WorkflowService()
        param = workflow_service.create_params_from_querystrings(request.query_params, user)
        result_raw = workflow_service.get_workflows(param)

        # フロントの形に合わせて整形する
        res_serializer = WorkflowsBodySerializer(result_raw)
        return Response(data=res_serializer.data)


class SysWorkflowAllDataView(SysAPIView):

    def get(self, request):
        """
        ワークフローのリスト
        stepや、各stepのtaskなどの情報も含む
        """
        user = self.request.user

        workflow_service = WorkflowService()
        param = workflow_service.create_params_from_querystrings(request.query_params, user)
        result_raw = workflow_service.get_workflow_all_data(param)

        # フロントの形に合わせて整形する
        res_serializer = WorkflowAllDataResponseBodySerializer(result_raw)
        return Response(data=res_serializer.data)


class SysSortWorkflowListView(SysListAPIView):
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
            wheres['name__contains'] = names
        if contract_id := request.query_params.get('contractId'):
            wheres['contract_id'] = contract_id
        if status := request.query_params.get('status'):
            wheres['status'] = status
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
                             .order_by('-type', 'account', '-id').all())

        queryset = workflow_list
        return queryset


class SysWorkflowDeleteView(SysAPIView):

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
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response("エラーが発生しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)
