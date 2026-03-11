import copy
import traceback
from collections import OrderedDict
from datetime import datetime
from typing import Optional

from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import Q, Prefetch, QuerySet
from django.utils.timezone import make_aware
from rest_framework import status

from conpass.mailer.workflow_mailer import WorkflowMailer
from conpass.mailer.bpo_task_mailer import BpoTaskMailer
from conpass.models import Workflow, WorkflowStep, WorkflowTask, WorkflowStepComment, WorkflowTaskUser, User, Contract, \
    ContractBody, MetaData, WorkflowTaskMaster, AdobeSetting, AdobeSign, File, AdobeSignApprovalUser, MetaKey, Group, \
    CorrectionRequest

from logging import getLogger

from conpass.models.constants import ContractTypeable
from conpass.models.constants.statusable import Statusable
from conpass.services.adobesign.adobesign_service import AdobeSignService

import json
import requests

from conpass.services.contract.contract_service import ContractService

logger = getLogger(__name__)


class WorkflowService:

    def get_workflows(self, params):
        """
        該当するワークフローの一覧を取得
        """
        wheres, where_sys = self._create_wheres(params)
        excludes = {
            'status': Workflow.Status.DISABLE.value,
        }
        # システムデフォルトテンプレート（=3）を先頭にするため、typeでソートする
        where_all = Q(**wheres)
        if where_sys:
            where_all = where_all | Q(**where_sys)
        return list(
            Workflow.objects.select_related('contract', 'client').exclude(**excludes).filter(where_all)
                    .order_by('-type', 'account', '-id').all())

    def get_workflow_all_data(self, params):
        """
        ワークフローの一式をすべて取得する
        ・ワークフロー
        ・ワークフローに紐づくステップ
        ・ステップに紐づくタスク
        ・ステップに紐づくコメント
        ・タスクに紐づくユーザ
        ・タスクに紐づくグループ
        """
        # query
        wheres, where_sys = self._create_wheres(params)
        excludes = {
            'status': Workflow.Status.DISABLE.value,
        }
        # システムデフォルトテンプレート（=3）を先頭にするため、typeでソートする
        where_all = Q(**wheres)
        if where_sys:
            where_all = where_all | Q(**where_sys)
        workflow_list = list(
            Workflow.objects.select_related('contract', 'client').exclude(**excludes).filter(where_all)
                    .order_by('-type', 'account', '-id').all())
        result_raw = []
        for workflow in workflow_list:
            # stepを探す
            wheres_step = {
                'status': WorkflowStep.Status.ENABLE.value,
                'workflow_id': workflow.id
            }
            workflow_step_list = list(WorkflowStep.objects.filter(**wheres_step).all())
            # step順に並べる
            workflow_step_list_sorted = self.sort_workflow_step(workflow_step_list)

            res_steps_raw = []
            for workflow_step in workflow_step_list_sorted:
                res_tasks_raw = self.get_workflow_step_task_list(workflow_step.id, workflow_step.workflow.id)
                workflow_step_comment_list = self.get_workflow_step_comment_list(workflow_step.id)
                res_steps_raw.append({
                    'step': workflow_step,
                    'tasks': res_tasks_raw,
                    'comments': workflow_step_comment_list,
                })
            result_raw.append({
                'workflow': workflow,
                'steps': res_steps_raw
            })

        return result_raw

    def _create_wheres(self, params: dict):
        wheres = {}
        wheres_sys = {}
        if params.get('account_id'):
            wheres['account_id'] = params.get('account_id')
        if params.get('client_id'):
            wheres['client_id'] = params.get('client_id')

        if params.get('id'):
            wheres['id'] = params.get('id')
        if params.get('name'):
            wheres['name__contains'] = params.get('name')
        if params.get('contract_id'):
            wheres['contract_id'] = params.get('contract_id')
        if params.get('status'):
            wheres['status'] = params.get('status')

        if params.get('workflowType'):
            if params.get('workflowType') == str(Workflow.Type.SYSTEM_TEMPLATE.value):
                wheres_sys = copy.deepcopy(wheres)
                wheres['type__in'] = [Workflow.Type.TEMPLATE.value, Workflow.Type.SYSTEM_TEMPLATE.value]
                wheres_sys['account_id'] = None
                wheres_sys['type'] = Workflow.Type.SYSTEM_TEMPLATE.value
            else:
                wheres['type'] = params.get('workflowType')
        return wheres, wheres_sys

    def sort_workflow_step(self, workflow_step_list: [WorkflowStep]) -> [WorkflowStep]:
        """
        ワークフローのステップを順番通りに並べ替える
        各ステップは親ステップ情報を持っているので、その順番になる
        """
        sorted_list = []
        parent = None
        while len(workflow_step_list) > 0:
            next_step = next(filter(lambda x: x.parent_step == parent, workflow_step_list), None)
            if next_step:
                workflow_step_list.remove(next_step)
                sorted_list.append(next_step)
                parent = next_step
            else:
                sorted_list.extend(workflow_step_list)
                break
        return sorted_list

    def get_workflow_step_data(self, step_id):
        """
        stepに紐づく情報を取得
        """
        wheres = {
            'status': WorkflowStep.Status.ENABLE.value,
            'id': step_id
        }
        workflow_step = WorkflowStep.objects.filter(**wheres).get()
        res_tasks_raw = self.get_workflow_step_task_list(step_id, workflow_step.workflow.id)
        workflow_step_comment_list = self.get_workflow_step_comment_list(step_id)
        return {
            'step': workflow_step,
            'tasks': res_tasks_raw,
            'comments': workflow_step_comment_list,
        }

    def get_workflow_step_task_list(self, step_id, workflow_id):
        """
        stepに紐づくtaskを取得
        """
        wheres = {
            'status': WorkflowTask.Status.ENABLE.value,
            'step_id': step_id
        }
        workflow_task_list = WorkflowTask.objects.select_related('task').filter(**wheres).all()
        res_tasks_raw = []
        for workflow_task in workflow_task_list:
            # user と group を探す
            wheres = {
                'status': WorkflowTaskUser.Status.ENABLE.value,
                'task_id': workflow_task.id
            }
            workflow_task_users_groups = WorkflowTaskUser.objects \
                .prefetch_related(Prefetch('user',
                                           queryset=User.objects.exclude(
                                               status=User.Status.DISABLE.value)))\
                .prefetch_related(Prefetch('group',
                                           queryset=Group.objects.exclude(
                                               status=Group.Status.DISABLE.value)))\
                .select_related('task').filter(**wheres)
            workflow_task_user_users = list(workflow_task_users_groups.exclude(user=None).all())
            workflow_task_user_groups = list(workflow_task_users_groups.exclude(group=None).all())

            # 電子署名（URL）の場合は署名用URLを取得してレスポンスに付与する
            adobe_sign_url = None
            if workflow_task.task.type == WorkflowTaskMaster.Type.SIGN_URL.value:
                # agreementIdを抽出
                try:
                    wheres = {
                        'status': AdobeSign.Status.ENABLE.value,
                        'workflow_id': workflow_id
                    }
                    adobe_sign = AdobeSign.objects.filter(**wheres).get()

                    user = adobe_sign.workflow.created_by
                    adobe_setting = AdobeSetting.objects.filter(account_id=user.account_id,
                                                                status=AdobeSetting.Status.ENABLE.value).get()

                    adobesign_service = AdobeSignService()
                    logger.info(f"agreement_id: {adobe_sign.agreement_id}")
                    r = adobesign_service.get_signing_url(adobe_sign.agreement_id, adobe_setting, user)
                    logger.info(r.text)
                    response_body = json.loads(r.text)
                    if r.status_code == status.HTTP_200_OK:
                        adobe_sign_url = response_body['signingUrlSetInfos'][0]['signingUrls'][0]['esignUrl']
                except AdobeSetting.DoesNotExist:
                    logger.info("API連携が完了しておりません")
                except AdobeSign.DoesNotExist:
                    logger.info(f"[電子署名URL取得失敗]AdobeSignが開始されていません。 workflow_id: {workflow_id}")
                except AdobeSign.MultipleObjectsReturned:
                    logger.info(f"[電子署名URL取得失敗]AdobeSignが複数開始されています。 workflow_id: {workflow_id}")

            res_tasks_raw.append({
                'task': workflow_task,
                'sign_url': adobe_sign_url,
                'users': workflow_task_user_users,
                'groups': workflow_task_user_groups
            })
        return res_tasks_raw

    def get_workflow_step_comment_list(self, step_id):
        """
        stepに紐づくコメントを取得
        """
        wheres = {
            'status': WorkflowStepComment.Status.ENABLE.value,
            'step_id': step_id
        }
        return list(WorkflowStepComment.objects.filter(**wheres).all())

    def clone_workflow(self, copyFrom: dict, workflowName: str, clone_type: int, renewal_contract_id: int, user: User):
        """テンプレートをがっつり複製する"""
        from_workflow = copyFrom.get('workflow')
        from_steps = copyFrom.get('steps')

        now = make_aware(datetime.now())

        workflow = self.create_workflow_clone(from_workflow, workflowName, clone_type, renewal_contract_id, user, now)

        pre_step = None
        for from_step_all in from_steps:
            workflow_step = self.create_workflow_step_clone(from_step_all, pre_step, workflow, user, now)
            pre_step = workflow_step

            from_task_alls = from_step_all.get('tasks')
            for from_task_all in from_task_alls:
                workflow_task = self.create_workflow_task_clone(from_task_all, workflow_step, user, now)

                from_users = from_task_all.get('users')
                for from_user in from_users:
                    self.create_workflow_task_user_group_clone(from_user, workflow_task, user, now)

                from_groups = from_task_all.get('groups')
                for from_group in from_groups:
                    self.create_workflow_task_user_group_clone(from_group, workflow_task, user, now)

        return workflow.id

    def create_workflow_clone(self, from_workflow: dict, name: str, clone_type: int, renewal_contract_id: int,
                              user: User, now: datetime) -> Workflow:
        try:
            workflow = Workflow()
            workflow.name = name
            workflow.account = user.account
            workflow.type = clone_type
            if from_workflow.get('contractId'):
                workflow.contract_id = from_workflow.get('contractId')
            workflow.client_id = from_workflow.get('clientId')
            if renewal_contract_id:
                workflow.renewal_from_contract_id = renewal_contract_id
            workflow.current_step_id = 0  # これはあとで
            workflow.is_rejected = False
            workflow.memo = from_workflow.get('memo')
            workflow.template_id = from_workflow.get('id')
            workflow.status = Workflow.Status.ENABLE.value
            workflow.created_at = now
            workflow.created_by = user
            workflow.updated_at = now
            workflow.updated_by = user
            workflow.save()
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
        return workflow

    def create_workflow_step_clone(self, from_step_all: dict, pre_step: Optional[WorkflowStep], workflow: Workflow,
                                   user: User, now: datetime) -> WorkflowStep:
        try:
            from_step = from_step_all.get('step')
            workflow_step = WorkflowStep()
            workflow_step.name = from_step.get('name')
            workflow_step.workflow = workflow
            workflow_step.parent_step = pre_step
            workflow_step.memo = from_step.get('memo')
            workflow_step.reject_step_count = from_step.get('rejectStepCount')
            workflow_step.start_date = from_step.get('startDate')
            workflow_step.end_date = None  # まだない
            workflow_step.expire_day = from_step.get('expireDay')
            workflow_step.status = WorkflowStep.Status.ENABLE.value
            workflow_step.created_at = now
            workflow_step.created_by = user
            workflow_step.updated_at = now
            workflow_step.updated_by = user
            workflow_step.save()
            if pre_step:
                pre_step.child_step = workflow_step
                pre_step.save()
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
        return workflow_step

    def create_workflow_task_clone(self, from_task_all: dict, workflow_step: WorkflowStep, user: User,
                                   now: datetime) -> WorkflowTask:
        try:
            from_task = from_task_all.get('task')
            workflow_task = WorkflowTask()
            workflow_task.name = from_task.get('name')
            workflow_task.step = workflow_step
            master = from_task.get('master')
            workflow_task.task_id = master.get('id') if master else None
            workflow_task.finish_condition = from_task.get('finishCondition')
            workflow_task.author_notify = from_task.get('authorNotify')
            workflow_task.status = WorkflowTask.Status.ENABLE.value
            workflow_task.created_at = now
            workflow_task.created_by = user
            workflow_task.updated_at = now
            workflow_task.updated_by = user
            workflow_task.save()
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
        return workflow_task

    def create_workflow_task_user_group_clone(self, from_user: dict, workflow_task: WorkflowTask, user: User,
                                              now: datetime) -> WorkflowTaskUser:
        try:
            workflow_task_user = WorkflowTaskUser()
            workflow_task_user.task = workflow_task
            workflow_task_user.user_id = from_user.get('user').get('id') if from_user.get('user') else None
            workflow_task_user.group_id = from_user.get('group').get('id') if from_user.get('group') else None
            workflow_task_user.is_finish = False
            workflow_task_user.status = WorkflowTaskUser.Status.ENABLE.value
            workflow_task_user.created_at = now
            workflow_task_user.created_by = user
            workflow_task_user.updated_at = now
            workflow_task_user.updated_by = user
            workflow_task_user.save()
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
        return workflow_task_user

    def start_workflow(self, workflow_id: int, directory_id: int, user: User):
        """
        ワークフローを開始する
        current_step_id が入る
        対象ワークフローに契約書テンプレートが指定されていたら、それを複製して契約書データを作る
        契約書テンプレートが指定されていないときは、空の契約書データを作る
        いずれにしても契約書が入る階層IDの指定が必要
        """
        param = {
            'account_id': user.account_id,
            'id': workflow_id
        }
        now = make_aware(datetime.now())

        try:
            workflow = Workflow.objects.filter(**param).get()
            if workflow.current_step_id != 0:
                raise Exception("ワークフローは既に開始されています")

            # 契約書の更新の場合、更新元契約書からデータをコピーする
            if workflow.renewal_from_contract_id:
                contract = self._copy_renewal_contract_data(workflow, directory_id, user, now)
            else:
                # 契約書テンプレートが指定されていた場合、テンプレートをコピーして契約書データを作る
                if workflow.contract_id:
                    contract = self._copy_contract_from_template(workflow.contract_id, directory_id, user, now)
                else:
                    contract = self._create_blank_contract(workflow.name, directory_id, workflow.client_id, user, now)

            # ステータスを仕掛中にする
            contract.status = Contract.Status.IN_PROCESS.value
            contract.save()

            workflow.contract_id = contract.id

            # 最初のステップを見つける
            param = {
                'workflow_id': workflow.id,
                'parent_step': None
            }
            workflow_step = WorkflowStep.objects.filter(**param).get()
            workflow_step.start_date = now
            workflow_step.updated_at = now
            workflow_step.updated_by = user
            workflow_step.save()

            workflow.current_step_id = workflow_step.id
            workflow.updated_at = now
            workflow.updated_by = user
            workflow.save()

            # 最初のタスク情報をメールで送信する
            self._send_next_task_mail(workflow_step, user)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
        except Workflow.DoesNotExist as e:
            logger.info(e)
            raise Exception("ワークフローが見つかりません")
        except WorkflowStep.DoesNotExist as e:
            logger.info(e)
            raise Exception("ワークフローのステップが見つかりません")

        return workflow.current_step_id

    def _copy_renewal_contract_data(self, workflow: Workflow, directory_id: int, user: User, now: datetime) -> Contract:
        """
        契約書更新用のワークフローでは、対象の契約書に更新元の契約書データの情報をコピーする
        ・契約書テンプレート
        ・契約書本文の最新
        ・階層
        ・契約開始日、契約終了日、解約ノーティス日以外のメタ情報（自由項目も含む）
        """
        # 更新元契約書情報を取得
        exclude = {
            'status': Contract.Status.DISABLE.value
        }
        wheres = {
            'id': workflow.renewal_from_contract_id,
            'account_id': user.account_id
        }
        try:
            renewal_from_contract = Contract.objects.exclude(**exclude).filter(**wheres).get()
        except Contract.DoesNotExist as e:
            logger.info(e)
            raise Exception("更新元の契約書が見つかりません")

        contract = copy.deepcopy(renewal_from_contract)
        contract.name = '{0}-{1}'.format(renewal_from_contract.name, now.replace(tzinfo=None).strftime('%Y%m%d%H%M%S'))
        contract.type = ContractTypeable.ContractType.CONTRACT.value
        contract.parent = renewal_from_contract
        contract.status = Contract.Status.ENABLE.value
        contract.created_at = now
        contract.created_by = user
        contract.updated_at = now
        contract.updated_by = user
        contract.id = None
        contract.save()

        # bodyは元の契約書の最新のものを複製する
        contract_body = renewal_from_contract.contract_body_contract.latest('updated_at')
        contract_body.id = None  # 新規作成にする
        contract_body.contract = contract
        contract_body.status = ContractBody.Status.ENABLE.value
        contract_body.created_at = now
        contract_body.created_by = user
        contract_body.updated_at = now
        contract_body.updated_by = user
        contract_body.version = "1.0"
        contract_body.is_adopted = False
        contract_body.save()

        # 全検索用モデルとMeilisearchに保存
        try:
            contract_service = ContractService()
            contract_service.save_contract_body_search_task(contract_body, now)
        except Exception as e:
            logger.error(f"contract_body_search error:{e}")

        # メタ情報をコピーする
        # ただし、以下は反映しない（空のメタデータは作る）
        # 契約日
        # 契約開始日
        # 契約終了日
        # 解約ノーティス日

        clears = ['contractdate', 'contractstartdate', 'contractenddate', 'cancelnotice']
        wheres = {
            'contract_id': renewal_from_contract.id,
            'status': MetaData.Status.ENABLE.value,
        }
        self._copy_metadata(contract, {}, wheres, [], clears, user, now)
        # 契約更新通知は「要」になる
        notify_label = "conpass_contract_renew_notify"
        wheres = {
            'status': MetaData.Status.ENABLE.value,
            'key__label': notify_label,
            'contract_id': contract.id,
        }
        try:
            metadata_notify = MetaData.objects.filter(**wheres).get()
            metadata_notify.value = "1"
            metadata_notify.save()
        except MetaData.DoesNotExist:
            # メタ情報「契約更新通知」が見つからないときは作る
            self._make_metadata(contract, notify_label, "1", None, user, now)

        return contract

    def _make_metadata(self, contract: Contract, label: str, value: str, date_value: Optional[datetime],
                       user: User, now: datetime):
        """
        メタ情報をラベルを指定して作成する
        ラベルがあるのでデフォルト前提
        """
        try:
            metakey = MetaKey.objects.get(label=label, type=MetaKey.Type.DEFAULT.value,
                                          status=MetaKey.Status.ENABLE.value)
        except MetaKey.DoesNotExist as e:
            logger.info(e)
            return

        metadata = MetaData()
        metadata.contract = contract
        metadata.key = metakey
        metadata.value = value
        metadata.date_value = date_value
        metadata.created_at = now
        metadata.created_by = user
        metadata.updated_at = now
        metadata.updated_by = user
        metadata.save()

    def _copy_contract_from_template(self, contract_template_id: int, directory_id: int, user: User,
                                     now: datetime) -> Contract:
        """
        契約書テンプレートから契約書を複製する
        もし複製元のタイプが契約書テンプレートではなかったら、そのまま返す
        directory_id: 複製先の契約書の階層
        """
        wheres = {
            'pk': contract_template_id,
            'account': user.account,
        }
        excludes = {
            'status': Contract.Status.DISABLE.value,
        }
        try:
            contract = Contract.objects.exclude(**excludes).filter(**wheres).get()
        except Contract.DoesNotExist as e:
            logger.info(e)
            raise Exception("契約書テンプレートが見つかりません")
        if contract.type != ContractTypeable.ContractType.TEMPLATE.value:
            if contract.directory_id != directory_id and directory_id > 0:
                contract.directory_id = directory_id
                contract.save()
            return contract

        adopted_version = str(contract.get_adopted_version())

        # 元の契約書テンプレートは使用済になる
        contract.status = Contract.Status.USED.value
        contract.created_at = now
        contract.created_by = user
        contract.updated_at = now
        contract.updated_by = user
        contract.save()

        contract.status = Contract.Status.ENABLE.value
        contract.type = ContractTypeable.ContractType.CONTRACT.value
        contract.id = None  # 新規作成にする
        if directory_id:
            contract.directory_id = directory_id
        contract.template_id = contract_template_id
        contract.save()

        # 契約書本文がまだ無い時は作っておく
        body_wheres = {
            'contract_id': contract_template_id,
            'version': adopted_version,
            'status': ContractBody.Status.ENABLE.value,
        }

        meta_wheres = {
            'contract_id': contract_template_id,
            'status': ContractBody.Status.ENABLE.value,
        }
        # 先に存在するか確認する。（見つからないまま取得するとDoesNotExistが発生してしまう)

        if ContractBody.objects.filter(**body_wheres).exists():
            contract_body = ContractBody.objects.filter(**body_wheres).latest('updated_at')
            contract_body.id = None  # 新規作成にする
        else:
            contract_body = ContractBody()
            contract_body.body = ""

        contract_body.contract = contract
        contract_body.created_at = now
        contract_body.created_by = user
        contract_body.updated_at = now
        contract_body.updated_by = user
        contract_body.version = "1.0"
        contract_body.is_adopted = False
        contract_body.save()

        # 全検索用モデルとMeilisearchに保存
        try:
            contract_service = ContractService()
            contract_service.save_contract_body_search_task(contract_body, now)
        except Exception as e:
            logger.error(f"contract_body_search error:{e}")

        # メタ情報があればそれも紐付け直す
        self._copy_metadata(contract, {}, meta_wheres, [], [], user, now)

        return contract

    def _create_blank_contract(self, name: str, directory_id: int, client_id: Optional[int], user: User,
                               now: datetime) -> Contract:
        """
        空の契約書データを作る
        種別は契約書に固定
        """
        contract = Contract()
        # 同じワークフローから作成されるケースが想定されるので、名前は一意な感じにする
        contract.name = '{0}-{1}'.format(name, now.replace(tzinfo=None).strftime('%Y%m%d%H%M%S'))
        contract.type = ContractTypeable.ContractType.CONTRACT.value
        if directory_id:
            contract.directory_id = directory_id
        contract.account = user.account
        contract.client_id = client_id
        # contract.is_provider = True
        contract.status = Contract.Status.ENABLE.value
        contract.created_at = now
        contract.created_by = user
        contract.updated_at = now
        contract.updated_by = user
        contract.save()
        contract.origin = contract
        # contract.parent = None
        contract.save()
        # 空のbodyも作る
        contract_body = ContractBody()
        contract_body.contract = contract
        contract_body.body = ''
        contract_body.status = ContractBody.Status.ENABLE.value
        contract_body.created_at = now
        contract_body.created_by = user
        contract_body.updated_at = now
        contract_body.updated_by = user
        contract_body.version = "1.0"
        contract_body.is_adopted = False
        contract_body.save()

        # 全検索用モデルとMeilisearchに保存
        try:
            contract_service = ContractService()
            contract_service.save_contract_body_search_task(contract_body, now)
        except Exception as e:
            logger.error(f"contract_body_search error:{e}")

        return contract

    def _copy_metadata(self, contract: Contract, excludes: dict, wheres: dict, clear_keys: list, clear_date_keys: list,
                       user: User, now: datetime):
        metadata_object = MetaData.objects
        if excludes:
            metadata_object = metadata_object.exclude(**excludes)
        if wheres:
            metadata_object = metadata_object.filter(**wheres)
        metadata_list = list(metadata_object.all())
        for metadata in metadata_list:
            if metadata.key.label in clear_keys:
                metadata.value = ""
            if metadata.key.label in clear_date_keys:
                metadata.date_value = None
            metadata.contract = contract
            metadata.created_at = now
            metadata.created_by = user
            metadata.updated_at = now
            metadata.updated_by = user
            metadata.id = None
        MetaData.objects.bulk_create(metadata_list)

        return metadata_list

    def finish_workflow_task(self, params: dict, user: User, now: Optional[datetime]):
        """
        ワークフローのタスクを誰かが完了した
        それに基づき、以下も判定して更新する
        タスク自体が完了したか（完了条件が一人or全員次第）
        ステップ自体が完了したか（ステップのすべてのタスクが完了）
        ワークフロー自体が完了したか（次のステップが無い）
        """
        result = {
            'task_finished': False,
            'step_finished': False,
            'workflow_finished': False
        }
        if not now:
            now = make_aware(datetime.now())

        wheres = {
            'id': params.get('taskUserId'),
            'task_id': params.get('taskId'),
            'status': WorkflowTaskUser.Status.ENABLE.value,
            'is_finish': False,  # まだ完了していないこと
        }
        try:
            workflow_task_user = WorkflowTaskUser.objects.filter(**wheres).get()
        except WorkflowTaskUser.DoesNotExist as e:
            logger.info(e)
            raise Exception("タスク担当者が見つかりません")

        in_user = workflow_task_user.user == user
        in_group_user = workflow_task_user.group is not None and workflow_task_user.group.user_group.filter(
            id=user.id).exists()
        if not in_user and not in_group_user:
            raise Exception("タスク担当者が見つかりません")

        # 以下全体トランザクション
        with transaction.atomic():
            workflow_task_user.is_finish = True
            workflow_task_user.updated_by = user
            workflow_task_user.updated_at = now
            workflow_task_user.save()

            # タスク完了かチェックする
            workflow_task = workflow_task_user.task
            task_finish = False
            if workflow_task.finish_condition == WorkflowTask.FinishCondition.ONE.value:
                task_finish = True
            else:
                # 全員が完了しているか確認する
                wheres = {
                    'task_id': params.get('taskId'),
                    'status': WorkflowTaskUser.Status.ENABLE.value,
                    'is_finish': False,  # まだ完了していないもの
                }
                if not WorkflowTaskUser.objects.filter(**wheres).exists():
                    task_finish = True

            result['task_finished'] = task_finish

            if task_finish:
                workflow_task.is_finish = True
                workflow_task.updated_by = user
                workflow_task.updated_at = now
                workflow_task.save()

                # 「タスク完了通知」が「通知する」ならタスク完了通知を送信
                if workflow_task.author_notify == WorkflowTask.AuthorNotifyCondition.TRUE.value:
                    self._send_notify_task_finish_mail(workflow_task, workflow_task.created_by)

                # 完了したタスクがBPOタスクの最後のタスク（[BPO]原本の保管または返却）の場合は、対象のワークフローのBPO依頼を「対応済」に更新する
                if workflow_task.task.type == WorkflowTaskMaster.Type.BPO_STORAGE_RETURN.value:
                    workflow_id = workflow_task.step.workflow.id
                    wheres = {'workflow_id': workflow_id}
                    CorrectionRequest.objects.filter(**wheres).update(
                        response=CorrectionRequest.Response.FINISHED.value,
                        updated_by_id=user.id,
                        updated_at=make_aware(datetime.now())
                    )

                # そのステップに含まれるタスクがすべて完了ならそのステップは完了
                workflow_step = workflow_task.step
                wheres = {
                    'step_id': workflow_step.id,
                    'status': WorkflowTask.Status.ENABLE.value,
                    'is_finish': False,  # まだ完了していないもの
                }
                if not WorkflowTask.objects.filter(**wheres).exists():
                    result['step_finished'] = True
                    workflow_step.end_date = now
                    workflow_step.updated_by = user
                    workflow_step.updated_at = now
                    workflow_step.save()
                    workflow = workflow_step.workflow
                    workflow.updated_by = user
                    workflow.updated_at = now
                    next_step = workflow_step.child_step
                    if next_step:
                        next_step.start_date = now
                        next_step.updated_by = user
                        next_step.updated_at = now
                        next_step.save()
                        workflow.current_step_id = next_step.id
                        # 次のステップに電子署名が入っているか調べる
                        has_esign = self._get_tasks_by_type(next_step, WorkflowTaskMaster.Type.SIGN)
                        has_esignurl = self._get_tasks_by_type(next_step, WorkflowTaskMaster.Type.SIGN_URL)
                        esign_task = None
                        if has_esign.exists():
                            esign_task = has_esign[0]
                        elif has_esignurl.exists():
                            esign_task = has_esignurl[0]
                        # 電子署名が存在する場合
                        if esign_task is not None:
                            # 契約書をadobeSignに作成
                            self.create_adobe_sign_agreement(esign_task, user, workflow, now)
                        self._send_next_task_mail(next_step, user)
                    else:  # 次のステップがなければワークフロー完了
                        workflow.current_step_id = 0
                        workflow.status = Workflow.Status.FINISHED.value
                        result['workflow_finished'] = True
                        self._finish_workflow_contract_task(workflow, workflow_step, user, now)
                    workflow.save()
                else:
                    self._send_next_task_mail(workflow_step, user)
        return result

    def _send_next_task_mail(self, step: WorkflowStep, user: User):
        wheres = {
            'step_id': step.id,
            'status': WorkflowTask.Status.ENABLE.value,
            'is_finish': False,  # まだ完了していないもの
        }
        task = WorkflowTask.objects.filter(**wheres).order_by('id').first()
        if task is not None:
            # 一つ前に完了したタスクを取得する
            wheres = {
                'step_id': step.id,
                'status': WorkflowTask.Status.ENABLE.value,
                'is_finish': True,
            }
            prev_task = WorkflowTask.objects.filter(**wheres).order_by('-id').first()
            # 一つ前のタスクが"[BPO契約管理者]承認"の場合、BPOタスクに移行するためBPO依頼を行う
            if prev_task is not None and prev_task.task.type == WorkflowTaskMaster.Type.BPO_ADMIN_APPROVE.value:
                # 代理押印か代理受取かチェック
                is_bpo_delegeted_stamp = task.task.type == WorkflowTaskMaster.Type.BPO_BOOKBUILDING_STAMP_MAIL.value
                self._send_bpo_task_mail(step, task, is_bpo_delegeted_stamp, user)

            # 未完了のタスクがある場合は次のタスク情報をメールでお知らせする
            wheres = {
                'task_id': task.id,
                'status': WorkflowTaskUser.Status.ENABLE.value,
            }
            workflow_task_users_groups = WorkflowTaskUser.objects \
                .prefetch_related(Prefetch('user',
                                           queryset=User.objects.exclude(
                                               status=User.Status.DISABLE.value)))\
                .prefetch_related(Prefetch('group',
                                           queryset=Group.objects.exclude(
                                               status=Group.Status.DISABLE.value))) \
                .select_related('task').filter(**wheres)
            workflow_task_user_users = list(workflow_task_users_groups.exclude(user=None).all())
            workflow_task_user_groups = list(workflow_task_users_groups.exclude(group=None).all())

            for taskuser in workflow_task_user_users:
                if taskuser.user.type != User.Type.CLIENT.value:
                    WorkflowMailer().send_next_task_request_mail(taskuser.user, task)

            for taskgroup in workflow_task_user_groups:
                wheres = {
                    'group': taskgroup.group_id,
                    'type': User.Type.ACCOUNT.value,
                    'status': User.Status.ENABLE.value,
                }
                users = list(User.objects.filter(**wheres).all())

                for user in users:
                    WorkflowMailer().send_next_task_request_mail(user, task)

    # [注意]呼び出し元でデータベーストランザクションを開始しておくこと
    def _send_bpo_task_mail(self, step: WorkflowStep, task: WorkflowTask, is_bpo_delegeted_stamp: bool, user: User):
        # BPOユーザーに作業する契約書を伝えるためにワークフローに紐づく契約書IDを取得する
        contract_id = step.workflow.contract.id
        workflow_id = step.workflow.id
        name = '代理押印' if is_bpo_delegeted_stamp else '代理受取'
        mail_body = (f"ワークフローID: {workflow_id}\nhttps://www.con-pass.jp/workflow/{workflow_id}\n\n",
                     "＜連絡先＞\n",
                     f"会社名：{step.workflow.client.name}\n",
                     f"住所：{step.workflow.client.corporate.address}\n",
                     f"代表者名：{step.workflow.client.corporate.executive_name}\n",
                     f"営業担当者名：{step.workflow.client.corporate.sales_name}\n",
                     f"電話番号：{step.workflow.client.corporate.tel}\n\n",
                     "＜ConPassユーザー＞\n",
                     f"顧客名：{step.workflow.account.name}\n")

        # WFタスク種別担当者名を追加する（BPOタスク以外のタスク）
        wheres = {
            'workflow_id': workflow_id,
            'status': WorkflowStep.Status.ENABLE.value
        }
        steps = list(WorkflowStep.objects.filter(**wheres).all())
        conpass_user_info = ''
        for st in steps:
            wheres = {
                'step_id': st.id,
                'status': WorkflowTask.Status.ENABLE.value
            }
            tasks = list(WorkflowTask.objects.filter(**wheres).all())
            for ts in tasks:
                bpo_task_types = [
                    WorkflowTaskMaster.Type.BPO_ADMIN_APPROVE.value,  # [BPO契約管理者]承認
                    WorkflowTaskMaster.Type.BPO_BOOKBUILDING_STAMP_MAIL.value,  # [BPO]印刷製本・押印・郵送
                    WorkflowTaskMaster.Type.BPO_RECEIPT.value,  # [BPO]受取
                    WorkflowTaskMaster.Type.BPO_SCANNING_UPLOAD.value,  # [BPO]スキャニング・アップロード
                    WorkflowTaskMaster.Type.BPO_STORAGE_RETURN.value  # [BPO]原本の保管または返却
                ]
                if ts.task.type in bpo_task_types:
                    continue
                wheres = {
                    'task_id': ts.id,
                    'status': WorkflowTaskUser.Status.ENABLE.value
                }
                users = list(WorkflowTaskUser.objects.filter(**wheres).all())
                names = ""
                for us in users:
                    names += us.group.name if us.group else us.user.username
                    names += ', '
                conpass_user_info += f"{ts.name} 担当者名：{names[:-2]}\n"

        mail_body = "".join(mail_body) + conpass_user_info

        # DBに保存
        try:
            contract = Contract.objects.get(id=contract_id)
            workflow = Workflow.objects.get(id=workflow_id)
            correction_request = CorrectionRequest()
            correction_request.name = name
            correction_request.body = mail_body
            correction_request.contract = contract
            correction_request.workflow = workflow
            correction_request.status = Statusable.Status.ENABLE.value
            correction_request.created_by_id = user.id
            correction_request.created_at = make_aware(datetime.now())
            correction_request.updated_by_id = user.id
            correction_request.updated_at = make_aware(datetime.now())
            correction_request.save()
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise Exception("DBエラーが発生しました")

        # メール送信
        # BPO契約管理者のメールアドレスに送信
        bpo_task_mailer = BpoTaskMailer()
        type_display = name

        # ユーザーはBPO契約書管理者にメールを送る
        account_id = step.workflow.account.id
        wheres = {
            'account_id': account_id,
            'is_bpo_admin': True,  # BPO契約管理者フラグ
            'status': User.Status.ENABLE.value,
        }
        bpo_admin_users = list(User.objects.filter(**wheres).all())
        for bpo_admin_user in bpo_admin_users:
            bpo_task_mailer.send_user_request_mail(bpo_admin_user, type_display, name, mail_body)
        bpo_task_mailer.send_admin_request_mail(user, type_display, name, mail_body)

    def _send_notify_task_finish_mail(self, workflow_task: WorkflowTask, created_by: User):
        if created_by.status == Statusable.Status.ENABLE.value:
            WorkflowMailer().send_notify_task_finish_mail(created_by, workflow_task)

    def _get_tasks_by_type(self, step: WorkflowStep, task_type: WorkflowTaskMaster.Type) -> QuerySet:
        """
        指定のステップに、指定のタスク種別のタスクがあるかどうか
        戻り値はQuerySet（複数）になります。あるかどうかを見たいときは exists()で判定してください
        """
        tasks = WorkflowTask.objects.select_related("task").filter(step=step,
                                                                   status=WorkflowTask.Status.ENABLE.value,
                                                                   task__type=task_type.value).all()
        if tasks.exists():
            return tasks.all()
        return tasks

    def _finish_workflow_contract_task(self, workflow: Workflow, workflow_step: WorkflowStep, user: User, now: datetime):
        # ワークフロー完了時に契約書のステータスなどを更新する
        contract = workflow.contract
        if not contract:
            return

        # 契約書が紐付いていて、そのステータスがSIGNEDでない場合はSIGNED_BY_PAPERにする
        # ただし、最後のタスクが電子署名の場合はSIGNED_BY_PAPERにしない（SIGNEDはwebhookが遅れて来て、そちらで変える）
        has_esign = self._get_tasks_by_type(workflow_step, WorkflowTaskMaster.Type.SIGN)
        has_esignurl = self._get_tasks_by_type(workflow_step, WorkflowTaskMaster.Type.SIGN_URL)
        if not has_esign.exists() and not has_esignurl.exists() and contract.status != Contract.Status.SIGNED.value:
            contract.status = Contract.Status.SIGNED_BY_PAPER.value
            contract.updated_by = user
            contract.updated_at = now
            contract.save()
        # この契約書に親があり、このワークフローが更新ワークフローであれば、親のメタ情報「契約更新通知」をオフにする
        if contract.parent and workflow.renewal_from_contract_id:
            wheres = {
                'status': MetaData.Status.ENABLE.value,
                'key__label': 'conpass_contract_renew_notify',
                'contract_id': contract.parent.id,
            }
            try:
                metadata_notify = MetaData.objects.filter(**wheres).get()
            except MetaData.DoesNotExist as e:
                logger.info(e)
                # メタ情報「契約更新通知」が見つからないときはスルー
                return
            metadata_notify.value = "0"
            metadata_notify.updated_by = user
            metadata_notify.updated_at = now
            metadata_notify.save()

    def reject_workflow_step(self, params: dict, user: User):
        wheres = {
            'id': params.get('stepId'),
            'status': WorkflowStep.Status.ENABLE.value,
        }
        now = make_aware(datetime.now())
        reject_count = params.get('rejectCount')
        workflow_step = WorkflowStep.objects.filter(**wheres).get()

        # 以下全体トランザクション
        with transaction.atomic():
            # 戻るカウントが1の場合、今のステップと戻ったステップで2のステップがリセットされる
            while reject_count >= 0:
                # 差し戻し対象のステップに電子署名が入っているか調べる
                esign_tasks = self._get_tasks_by_type(workflow_step, WorkflowTaskMaster.Type.SIGN)
                esignurl_tasks = self._get_tasks_by_type(workflow_step, WorkflowTaskMaster.Type.SIGN_URL)
                # 電子署名が存在する場合
                if esign_tasks.exists() or esignurl_tasks.exists():
                    # 契約書のキャンセル
                    try:
                        self.cancel_agreements_state(workflow_step.workflow, user, now)
                    except Exception:
                        # TODO:adobesign のキャンセル失敗時の対応
                        # 既に完了している場合もある
                        pass
                self.clear_workflow_task(workflow_step.id, user, now)
                # 開始日、完了日もリセット
                workflow_step.start_date = now if reject_count == 0 else None
                workflow_step.end_date = None
                workflow_step.updated_by = user
                workflow_step.updated_at = now
                workflow_step.save()
                if reject_count > 0:
                    workflow_step = workflow_step.parent_step
                reject_count -= 1

            # ワークフローのステップ位置をかえる
            workflow = workflow_step.workflow
            workflow.current_step_id = workflow_step.id
            workflow.updated_by = user
            workflow.updated_at = now
            workflow.save()

            # 差し戻し後のステップが電子署名か調べる
            esign_tasks = self._get_tasks_by_type(workflow_step, WorkflowTaskMaster.Type.SIGN)
            esignurl_tasks = self._get_tasks_by_type(workflow_step, WorkflowTaskMaster.Type.SIGN_URL)
            esign_task = None
            if esign_tasks.exists():
                esign_task = esign_tasks[0]  # 基本的に１ワークフロー内では１電子署名とします
            elif esignurl_tasks.exists():
                esign_task = esignurl_tasks[0]  # 基本的に１ワークフロー内では１電子署名とします
            # 電子署名が存在する場合
            if esign_task is not None:
                # 契約書をadobeSignに作成（署名依頼も含む）
                self.create_adobe_sign_agreement(esign_task, user, workflow, now)
            # 次のタスク情報をメールで送信する
            self._send_next_task_mail(workflow_step, user)

    def clear_workflow_task(self, step_id: int, user: User, now: datetime):
        """
        ワークフローの該当ステップに紐づくタスクを未完了に戻す
        """
        wheres = {
            'step_id': step_id,
            'status': WorkflowTask.Status.ENABLE.value,
        }
        try:
            workflow_tasks = list(WorkflowTask.objects.filter(**wheres).all())
        except WorkflowStep.DoesNotExist as e:
            logger.info(e)
            raise Exception("ワークフローのステップが見つかりません")
        for workflow_task in workflow_tasks:
            workflow_task.is_finish = False
            workflow_task.updated_by = user
            workflow_task.updated_at = now
            workflow_task.save()

            # タスクに紐づく担当者の完了もすべて戻す
            wheres = {
                'task_id': workflow_task.id,
                'status': WorkflowTaskUser.Status.ENABLE.value,
            }
            workflow_task_users = list(WorkflowTaskUser.objects.filter(**wheres).all())
            for taskuser in workflow_task_users:
                taskuser.is_finish = False
                taskuser.updated_by = user
                taskuser.updated_at = now
            WorkflowTaskUser.objects.bulk_update(workflow_task_users, fields=['is_finish', 'updated_by', 'updated_at'])

    def get_workflow_mytask_list(self, user: User):
        # 自分もしくは自分が含まれるグループのタスクで未完了のものを探す
        # 紐づくワークフローはテンプレートではなくて、稼働中であること
        wheres = {
            'status': WorkflowTaskUser.Status.ENABLE.value,
            'is_finish': False,
        }
        try:
            user_group_ids = user.group.all()
            workflow_task_users = list(
                WorkflowTaskUser.objects.filter(**wheres).filter(Q(user=user) | Q(group__in=user_group_ids)).order_by(
                    '-task__step__start_date', 'id').all())
            workflow_task_users = list(filter(
                lambda tu: (tu.task.step.workflow.status == Workflow.Status.ENABLE.value) and (
                    tu.task.step.workflow.type == Workflow.Type.WORKFLOW.value) and (
                    tu.task.step.workflow.current_step_id == tu.task.step_id), workflow_task_users))
        except Exception as e:
            raise e
        return workflow_task_users

    def add_step_comment(self, step_id: int, user: User, comment: str, now: datetime):
        wheres = {
            'id': step_id,
            'status': WorkflowStep.Status.ENABLE.value
        }
        try:
            workflow_step = WorkflowStep.objects.filter(**wheres).get()
        except WorkflowStep.DoesNotExist as e:
            logger.info(e)
            raise e

        # workflowがaccountに紐付いているかも確認する
        # 連絡先ユーザの場合は連絡先に紐付いているかどうか
        found = False
        if user.type == User.Type.ACCOUNT.value and workflow_step.workflow.account == user.account:
            found = True
        elif user.type == User.Type.CLIENT.value and workflow_step.workflow.account.id == user.client.provider_account_id:
            found = True
        elif user.type == User.Type.ADMIN.value:
            found = True
        if not found:
            raise WorkflowStep.DoesNotExist

        workflow_step_comment = WorkflowStepComment()
        workflow_step_comment.step = workflow_step
        workflow_step_comment.comment = comment
        workflow_step_comment.user = user
        workflow_step_comment.status = WorkflowStepComment.Status.ENABLE.value
        workflow_step_comment.created_at = now
        workflow_step_comment.created_by = user
        workflow_step_comment.updated_at = now
        workflow_step_comment.updated_by = user
        workflow_step_comment.save()

        return workflow_step_comment.id

    def create_adobe_sign_agreement(self, esign_task: WorkflowTask, user: User, workflow: Workflow,
                                    now: datetime):
        try:
            adobe_setting = AdobeSetting.objects.filter(account_id=user.account_id,
                                                        status=AdobeSetting.Status.ENABLE.value).get()
        except AdobeSetting.DoesNotExist as e:
            logger.info(e)
            raise Exception("API連携が完了しておりません")

        # transientDocumentIdの取得
        transient_document_id = self.create_transient_documents(adobe_setting, workflow, user)

        # agreementsIdの取得
        agreements_id = self.create_agreements(adobe_setting, transient_document_id, esign_task, user, workflow)

        adobe_sign = AdobeSign()
        adobe_sign.contract = workflow.contract
        adobe_sign.workflow = workflow
        adobe_sign.agreement_id = agreements_id
        adobe_sign.transient_document_id = transient_document_id
        adobe_sign.status = AdobeSign.Status.ENABLE.value
        adobe_sign.created_at = now
        adobe_sign.created_by = user
        adobe_sign.updated_at = now
        adobe_sign.updated_by = user
        adobe_sign.save()

        # そのタスクに含まれる担当者一覧を取得
        esign_taskusers = list(WorkflowTaskUser.objects.filter(task=esign_task,
                                                               status=WorkflowTaskUser.Status.ENABLE.value).order_by(
            'id').all())

        for task_user in esign_taskusers:
            adobe_sign_approval_user = AdobeSignApprovalUser()
            adobe_sign_approval_user.adobesign = adobe_sign
            adobe_sign_approval_user.user = task_user.user
            adobe_sign_approval_user.approval_mail_address = task_user.user.email
            adobe_sign_approval_user.status = AdobeSignApprovalUser.Status.ENABLE.value
            adobe_sign_approval_user.created_at = now
            adobe_sign_approval_user.created_by = task_user.user
            adobe_sign_approval_user.updated_at = now
            adobe_sign_approval_user.updated_by = task_user.user
            adobe_sign_approval_user.save()

    def create_transient_documents(self, adobe_setting: AdobeSetting, workflow: Workflow, user: User):
        # AdobeSignの transientDocument を作成
        # workflowの契約書の本文をもとにpdfを作成、それを利用します
        adobesign_service = AdobeSignService()
        r = adobesign_service.transient_documents(workflow, adobe_setting, user)
        context = json.loads(r.text)
        if 'code' in context:
            error_params = {
                'code': context['code'],
                'message': context['message'],
            }
            raise Exception(error_params)
        return context['transientDocumentId']

    def create_agreements(self, adobe_setting: AdobeSetting, transient_document_id, esign_task: WorkflowTask, user: User,
                          workflow: Workflow):
        endpoint = 'https://api.jp1.adobesign.com:443/api/rest/v6/agreements'

        access_token = adobe_setting.access_token

        # headerでコンテンツタイプを指定
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + access_token,
        }

        # そのタスクに含まれる担当者一覧を取得
        esign_taskusers = list(WorkflowTaskUser.objects.filter(task=esign_task,
                                                               status=WorkflowTaskUser.Status.ENABLE.value).order_by(
            'id').all())

        participant_sets_info = []
        for i, task_user in enumerate(esign_taskusers):
            i += 1
            params = {
                "memberInfos": [
                    {
                        "email": task_user.user.email
                    }
                ],
                "order": i,
                "role": "SIGNER",
            }
            participant_sets_info.append(params)
        data = {
            "fileInfos": [
                {
                    "transientDocumentId": transient_document_id
                }
            ],
            "name": '電子署名：' + workflow.contract.name,
            "participantSetsInfo": participant_sets_info,
            "signatureType": "ESIGN",
            "state": "IN_PROCESS"
        }

        # 契約書の署名依頼
        r = requests.post(url=endpoint, headers=headers, data=json.dumps(data))
        context = json.loads(r.text)
        if 'code' in context:
            error_params = {
                'code': context['code'],
                'message': context['message'],
            }
            raise Exception(error_params)
        return context['id']

    def cancel_agreements_state(self, workflow: Workflow, user: User, now: datetime):
        try:
            adobe_setting = AdobeSetting.objects.filter(account_id=user.account_id,
                                                        status=AdobeSetting.Status.ENABLE.value).get()
        except AdobeSetting.DoesNotExist as e:
            logger.info(e)
            raise Exception("API連携が完了しておりません")

        access_token = adobe_setting.access_token

        adobe_sign = AdobeSign.objects.filter(workflow_id=workflow.id, contract_id=workflow.contract.id,
                                              status=AdobeSign.Status.ENABLE.value).order_by('-created_at',
                                                                                             'id').first()
        if not adobe_sign:
            raise Exception("AdobeSignデータがありません")
        url = '{0}api/rest/v6/agreements/{1}/state'
        endpoint = url.format(settings.ADOBESIGN_API_ACCESS_POINT, adobe_sign.agreement_id)

        # headerでコンテンツタイプを指定
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + access_token,
        }

        data = {
            'state': 'CANCELLED'
        }

        # 契約書のキャンセル
        requests.put(url=endpoint, headers=headers, data=json.dumps(data))

        adobe_sign.status = AdobeSign.Status.DISABLE.value
        adobe_sign.updated_at = now
        adobe_sign.updated_by = user
        adobe_sign.save()

        adobe_sign_approval_users = AdobeSignApprovalUser.objects.filter(adobesign=adobe_sign,
                                                                         status=AdobeSignApprovalUser.Status.ENABLE.value).all()

        for approval_user in adobe_sign_approval_users:
            approval_user.status = AdobeSignApprovalUser.Status.DISABLE.value
            approval_user.updated_at = now
            approval_user.updated_by = user
            approval_user.save()

    def edit_whole_workflow(self, request_data, login_user: User):

        now = make_aware(datetime.now())
        # ワークフローを作る
        try:
            workflow = self._get_or_create_workflow(request_data, login_user, now)
        except Workflow.DoesNotExist as e:
            logger.info(e)
            raise e
        # 一度紐付いていたステップはすべて無効にする（削除対応）
        disable_steps = list(
            WorkflowStep.objects.exclude(status=WorkflowStep.Status.DISABLE.value).filter(workflow=workflow).all())
        bulk_steps = []
        for step in disable_steps:
            step.status = WorkflowStep.Status.DISABLE.value
            step.updated_by = login_user
            step.updated_at = now
            bulk_steps.append(step)
        WorkflowStep.objects.bulk_update(bulk_steps, fields=['status', 'updated_by', 'updated_at'])
        # ワークフローのステップおよび、それに紐づくタスク、ユーザ、グループを作る
        pre_step = None
        steps = request_data.get('steps')
        for step in steps:
            try:
                workflow_step = self._create_workflow_step(step, pre_step, workflow, login_user, now)
                pre_step = workflow_step
            except WorkflowStep.DoesNotExist as e:
                logger.info(e)
                raise e
            # 一度紐付いていたタスクおよび、それに紐づく担当者は一旦すべて無効にする（削除対応）
            disable_tasks = list(WorkflowTask.objects.exclude(status=WorkflowTask.Status.DISABLE.value).filter(
                step=workflow_step).all())
            bulk_tasks = []
            bulk_taskusers = []
            for task in disable_tasks:
                disable_taskusers = list(
                    WorkflowTaskUser.objects.exclude(status=WorkflowTaskUser.Status.DISABLE.value).filter(
                        task=task).all())
                for taskuser in disable_taskusers:
                    taskuser.status = WorkflowTaskUser.Status.DISABLE.value
                    taskuser.updated_by = login_user
                    taskuser.updated_at = now
                    bulk_taskusers.append(taskuser)
                task.status = WorkflowTask.Status.DISABLE.value
                task.updated_by = login_user
                task.updated_at = now
                bulk_tasks.append(task)
            WorkflowTask.objects.bulk_update(bulk_tasks, fields=['status', 'updated_by', 'updated_at'])
            WorkflowTaskUser.objects.bulk_update(bulk_taskusers, fields=['status', 'updated_by', 'updated_at'])
            # ステップに紐づくタスクを作る
            for task in step.get('tasks'):
                try:
                    workflow_task = self._create_workflow_task(task, workflow_step, login_user, now)
                except WorkflowTask.DoesNotExist as e:
                    logger.info(e)
                    raise e
                # タスクに紐づくユーザを作る
                # テンプレートの場合空欄もありうる
                users = task.get('users')
                groups = task.get('groups')
                for user in users:
                    try:
                        self._create_workflow_task_user_group(user.get('user'), None, workflow_task, login_user,
                                                              now)
                    except WorkflowTaskUser.DoesNotExist as e:
                        logger.info(e)
                        raise e
                # タスクに紐づくグループを作る。modelはtaskuserと兼用
                # テンプレートの場合空欄もありうる
                for group in groups:
                    try:
                        self._create_workflow_task_user_group(None, group.get('group'), workflow_task, login_user,
                                                              now)
                    except WorkflowTaskUser.DoesNotExist as e:
                        logger.info(e)
                        raise e
        return workflow.id

    # 編集用のワークフローを取得
    # id指定がなければ新規作成
    def _get_or_create_workflow(self, request_data: OrderedDict, login_user: User, now: datetime):
        if login_user.type != User.Type.ADMIN.value:
            set_account = login_user.account_id
        else:
            set_account = request_data.get('account')
        if request_data.get('id'):
            wheres = {
                'id': request_data.get('id')
            }
            # ログインユーザがシステム管理者の場合はアカウント縛りをしない
            if login_user.type != User.Type.ADMIN.value:
                wheres['account_id'] = login_user.account_id
            try:
                workflow = Workflow.objects.get(**wheres)
            except Workflow.DoesNotExist as e:
                logger.info(e)
                raise e
        else:
            workflow = Workflow()
        workflow.type = request_data.get('workflowType')
        workflow.name = request_data.get('name')
        if set_account:
            workflow.account_id = set_account
        else:
            workflow.account = None
        # パラメータで'0'が送られてきた場合には設定を削除するためにNoneに変換する
        if request_data.get('contract'):
            workflow.contract_id = request_data.get('contract')
        else:
            workflow.contract_id = None
        # パラメータで'0'が送られてきた場合には設定を削除するためにNoneに変換する
        if request_data.get('client'):
            workflow.client_id = request_data.get('client')
        else:
            workflow.client_id = None
        workflow.memo = request_data.get('memo')
        workflow.current_step_id = 0  # この後で指定する
        workflow.is_rejected = request_data.get('isRejected')
        if not request_data.get('id'):
            workflow.created_at = now
            workflow.created_by = login_user
        workflow.updated_at = now
        workflow.updated_by = login_user
        workflow.status = Workflow.Status.ENABLE.value
        workflow.save()  # ID確定させる
        return workflow

    # ワークフローのステップを作る
    def _create_workflow_step(self, step: OrderedDict, pre_step: Optional[WorkflowStep], workflow: Workflow,
                              login_user: User,
                              now: datetime):
        if step.get('id') > 0:
            workflow_step = WorkflowStep.objects.get(pk=step.get('id'))
        else:
            workflow_step = WorkflowStep()
        workflow_step.name = step.get('name')
        workflow_step.parent_step = pre_step
        workflow_step.child_step = None
        workflow_step.expire_day = step.get('expireDay')
        workflow_step.reject_step_count = step.get('rejectStepCount')
        workflow_step.workflow = workflow
        workflow_step.start_date = None
        workflow_step.end_date = None
        if step.get('id') == 0:
            workflow_step.created_at = now
            workflow_step.created_by = login_user
        workflow_step.updated_at = now
        workflow_step.updated_by = login_user
        workflow_step.status = WorkflowStep.Status.ENABLE.value
        workflow_step.save()  # ID確定させる
        if pre_step:
            pre_step.child_step = workflow_step
            pre_step.save()
        return workflow_step  # これが次のpre_stepになる

    # ステップに紐づくタスクを作る
    def _create_workflow_task(self, task: OrderedDict, workflow_step: WorkflowStep, login_user: User,
                              now: datetime):
        if task.get('id') > 0:
            workflow_task = WorkflowTask.objects.get(pk=task.get('id'))
        else:
            workflow_task = WorkflowTask()
        workflow_task.name = task.get('name')
        workflow_task.step = workflow_step
        workflow_task.task_id = task.get('masterId') if task.get('masterId') > 0 else None
        workflow_task.finish_condition = task.get('finishCondition')
        workflow_task.author_notify = task.get('authorNotify')
        if task.get('id') == 0:
            workflow_task.created_at = now
            workflow_task.created_by = login_user
        workflow_task.updated_at = now
        workflow_task.updated_by = login_user
        workflow_task.status = WorkflowTask.Status.ENABLE.value
        workflow_task.save()  # ID確定させる
        return workflow_task

    # タスクに紐づくユーザかグループを作る。modelは兼用
    def _create_workflow_task_user_group(self, user: Optional[OrderedDict], group: Optional[OrderedDict],
                                         workflow_task: WorkflowTask,
                                         login_user: User, now: datetime):
        workflow_task_user = WorkflowTaskUser()
        workflow_task_user.task = workflow_task
        if user:
            workflow_task_user.user_id = user.get('id')
        if group:
            workflow_task_user.group_id = group.get('id')
        workflow_task_user.is_finish = False
        workflow_task_user.created_at = now
        workflow_task_user.created_by = login_user
        workflow_task_user.updated_at = now
        workflow_task_user.updated_by = login_user
        workflow_task_user.status = WorkflowTaskUser.Status.ENABLE.value
        workflow_task_user.save()

    def create_params_from_querystrings(self, query_params: dict, user: User):
        """
        ワークフロー取得系APIのパラメータから検索条件への対応をする
        """
        param = {}
        if user.type == User.Type.ACCOUNT.value:
            param['account_id'] = user.account_id
        elif user.type == User.Type.CLIENT.value:
            # 連絡先ユーザも参照できる
            param['account_id'] = user.client.provider_account_id
            param['client_id'] = user.client.id

        if workflow_id := query_params.get('id'):
            param['id'] = workflow_id
        if workflow_type := query_params.get('workflowType'):
            if workflow_type != '0':
                param['workflowType'] = workflow_type
        if name := query_params.get('name'):
            param['name'] = name
        if contract_id := query_params.get('contractId'):
            param['contract_id'] = contract_id
        if status := query_params.get('status'):
            param['status'] = status

        return param
