from enum import Enum, unique
from django.db import models
from conpass.models import User, Contract, WorkflowParam, Account, Client
from conpass.models.constants.statusable import Statusable


class Workflow(models.Model, Statusable):
    """
    ワークフロー
    ワークフローにはステップが１つ以上あり
    　各ステップにはタスクが１つ以上あり
    　　各タスクには担当になるユーザもしくはグループが１つ以上ある
    is_rejected はリジェクトされた直後に立つ。表示制御用
    """

    class Type(Enum):
        WORKFLOW = 1  # 実際のワークフロー
        TEMPLATE = 2  # ワークフローのテンプレート
        SYSTEM_TEMPLATE = 3  # システムで用意したワークフローのテンプレート。編集、削除不可

    class Status(Enum):
        DISABLE = 0
        ENABLE = 1
        FINISHED = 2  # 完了した

    name = models.CharField(max_length=255)  # 名前
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING, related_name='workflow_account',
                                blank=True, null=True, default=None)  # アカウントID
    contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING, related_name='workflow_contract',
                                 blank=True, null=True, default=None)  # 契約書ID（あれば）
    renewal_from_contract = models.ForeignKey(Contract, on_delete=models.DO_NOTHING,
                                              related_name='workflow_renewal_from_contract',
                                              blank=True, null=True, default=None)  # 契約更新時の元になる契約書
    client = models.ForeignKey(Client, on_delete=models.DO_NOTHING,
                               related_name='workflow_client', blank=True, null=True,
                               default=None)  # 取引先（連絡先）ID typeが取引先の場合
    current_step_id = models.IntegerField()  # 現在のワークフローのステップID
    type = models.IntegerField(default=Type.WORKFLOW.value)  # 種別（テンプレートか実際のワークフローか）
    is_rejected = models.BooleanField(default=False)  # リジェクトされた状態か
    memo = models.CharField(max_length=255, blank=True, default="")  # 備考
    params = models.ManyToManyField(WorkflowParam, related_name='workflow_param', blank=True)
    template = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='workflow_template',
                                 blank=True, null=True, default=None)  # 元にしたワークフローテンプレートID（ない場合もある）
    status = models.IntegerField(default=Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='workflow_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='workflow_updated_by', blank=True,
                                   null=True, default=None)  # 更新者

    def __str__(self):
        return self.name
