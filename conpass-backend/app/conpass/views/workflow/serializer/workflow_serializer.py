from rest_framework import serializers

from conpass.models import Workflow
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy
from conpass.views.common.recursive_field import RecursiveField
from conpass.views.contract.serializer.contract_item_serializer import ContractItemResponseSerializer


class WorkflowListRequestBodySerializer(serializers.Serializer):
    workflowType = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class WorkflowTaskResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()  # 名前
    step = serializers.DjangoModelField('WorkflowStep')  # ワークフローのステップID
    task = serializers.DjangoModelField('WorkflowTaskMaster')  # ワークフローのタスクマスタID
    finishCondition = serializers.IntegerField(source='finish_condition')  # タスクの完了条件（紐づく全員が完了、or一人が完了）
    authorNotify = serializers.IntegerField(source='author_notify')  # タスク完了時に申請者にメールを送信するかどうか
    status = serializers.IntegerField()  # ステータス（有効無効）
    createdAt = serializers.DateTimeField(source='created_at')  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at')  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者


class WorkflowStepResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    rejectStepCount = serializers.IntegerField(source='reject_step_count')  # 差し戻しステップ数
    parentStep = serializers.DjangoModelField(verbose_name="WorkflowStep")  # 親ステップID blankは始点
    childStep = serializers.DjangoModelField(verbose_name="WorkflowStep")  # 子ステップID blankは終点
    memo = serializers.CharField()
    startDate = serializers.DateTimeField(source='start_date')  # 本ステップが開始された日時
    endDate = serializers.DateTimeField(source='end_date')  # 本ステップが完了した日時
    expireDay = serializers.IntegerField(source='expire_day')  # ステップの期限
    createdAt = serializers.DateTimeField(source='created_at')  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at')  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者


class WorkflowListResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 名前
    accountName = serializers.CharField(source='account.name', allow_null=True)
    accountId = serializers.IntegerField(source='account.id', default=0)
    contractName = serializers.CharField(source='contract.name', allow_null=True)  # 契約書ID（あれば）
    clientName = serializers.CharField(source='client.name', allow_null=True)  # 契約書ID（あれば）
    currentStepId = serializers.IntegerField(source='current_step_id')  # 現在のワークフローのステップID
    workflowType = serializers.IntegerField(source='type')  # 種別（テンプレートか実際のワークフローか）
    isRejected = serializers.BooleanField(source='is_rejected')  # リジェクトされた状態か
    memo = serializers.CharField()  # 備考
    template = serializers.CharField()  # 備考
    status = serializers.IntegerField()  # ステータス（有効無効）
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者


class WorkflowUserRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ユーザID


class WorkflowGroupRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()  # グループID


class WorkflowTaskUserRequestBodySerializer(serializers.Serializer):
    user = WorkflowUserRequestBodySerializer()


class WorkflowTaskGrouRequestBodySerializer(serializers.Serializer):
    group = WorkflowGroupRequestBodySerializer()


class WorkflowTaskRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID。新規作成時はnull
    name = serializers.CharField(max_length=255)
    masterId = serializers.IntegerField()
    finishCondition = serializers.IntegerField()
    authorNotify = serializers.IntegerField()
    users = serializers.ListField(
        child=WorkflowTaskUserRequestBodySerializer(),
        allow_empty=True,
    )
    groups = serializers.ListField(
        child=WorkflowTaskGrouRequestBodySerializer(),
        allow_empty=True,
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        if not data.get('users') and not data.get('groups'):
            raise serializers.ValidationError("ユーザかグループを指定してください。")
        return data


class WorkflowTemplateTaskRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID。新規作成時はnull
    name = serializers.CharField(max_length=255)
    masterId = serializers.IntegerField()
    finishCondition = serializers.IntegerField()
    authorNotify = serializers.IntegerField()
    users = serializers.ListField(
        child=WorkflowTaskUserRequestBodySerializer(),
        allow_empty=True,
    )
    groups = serializers.ListField(
        child=WorkflowTaskGrouRequestBodySerializer(),
        allow_empty=True,
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        # テンプレート時はユーザ、グループ指定が無くても良い
        # if not data.get('users') and not data.get('groups'):
        #     raise serializers.ValidationError("ユーザかグループを指定してください。")
        return data


class WorkflowStepRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID。新規作成時はnull
    name = serializers.CharField(max_length=255)
    expireDay = serializers.IntegerField()  # ステップの期限
    rejectStepCount = serializers.IntegerField(default=1)  # 差し戻しステップ数
    tasks = serializers.ListField(
        child=WorkflowTaskRequestBodySerializer()
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        if not data.get('tasks'):
            raise serializers.ValidationError("タスクを指定してください。")
        return data


class WorkflowTemplateStepRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID。新規作成時はnull
    name = serializers.CharField(max_length=255)
    expireDay = serializers.IntegerField()  # ステップの期限
    rejectStepCount = serializers.IntegerField(default=1)  # 差し戻しステップ数
    tasks = serializers.ListField(
        child=WorkflowTemplateTaskRequestBodySerializer()
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        if not data.get('tasks'):
            raise serializers.ValidationError("タスクを指定してください。")
        return data


class WorkflowEditRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID。新規作成時はnull
    name = serializers.CharField(max_length=255, default="")
    account = serializers.IntegerField(allow_null=True, required=False)
    contract = serializers.IntegerField(allow_null=True, required=False)
    client = serializers.IntegerField(allow_null=True, required=False)
    workflowType = serializers.IntegerField()  # 種別（テンプレートか実際のワークフローか）
    isRejected = serializers.BooleanField()  # 種別（テンプレートか実際のワークフローか）
    memo = serializers.CharField(max_length=255, allow_blank=True, default="")  # 備考
    steps = serializers.ListField(
        child=WorkflowStepRequestBodySerializer()
    ) if workflowType == Workflow.Type.WORKFLOW.value else (
        serializers.ListField(
            child=WorkflowTemplateStepRequestBodySerializer()
        )
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        if not data.get('steps'):
            raise serializers.ValidationError("ステップを指定してください。")
        return data


class WorkflowTaskMasterResponseSerializer(serializers.Serializer):
    """
    ワークフローのタスクのマスタデータは基本的にあまり変更は無い想定
    必要なものだけ返す
    """
    id = serializers.IntegerField()
    name = serializers.CharField()  # 名前
    description = serializers.CharField()  # タスクの内容
    taskType = serializers.IntegerField(source='type')  # タスクの種別（承認、送信、郵送、印刷など）
    isNeedContract = serializers.BooleanField(source='is_need_contract')


class WorkflowTaskMasterResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListField(
        child=WorkflowTaskMasterResponseSerializer()
    )


class WorkflowAllDataGroupResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    users = UserResponseSerializerEasy(source='user_group', many=True)  # グループに所属しているユーザー


class WorkflowAllDataTaskUserGroupResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    isFinish = serializers.BooleanField(source='is_finish')
    user = UserResponseSerializerEasy(allow_null=True)
    group = WorkflowAllDataGroupResponseSerializer(allow_null=True)


class WorkflowAllDataTaskMasterResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    type = serializers.IntegerField()
    isNeedContract = serializers.BooleanField(source='is_need_contract')


class WorkflowAllDataTaskRawResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    isFinish = serializers.BooleanField(source='is_finish')
    finishCondition = serializers.IntegerField(source='finish_condition')
    authorNotify = serializers.IntegerField(source='author_notify')
    master = WorkflowAllDataTaskMasterResponseSerializer(source='task')


class WorkflowAllDataTaskResponseSerializer(serializers.Serializer):
    task = WorkflowAllDataTaskRawResponseSerializer()
    signUrl = serializers.CharField(source='sign_url')
    users = serializers.ListField(
        child=WorkflowAllDataTaskUserGroupResponseSerializer()
    )
    groups = serializers.ListField(
        child=WorkflowAllDataTaskUserGroupResponseSerializer()
    )


class WorkflowAllDataCommentResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    comment = serializers.CharField()
    user = UserResponseSerializerEasy()
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")


class WorkflowAllDataStepRawResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    memo = serializers.CharField()
    parentStepId = serializers.IntegerField(source='parent_step_id')
    childStepId = serializers.IntegerField(source='child_step_id')
    rejectStepCount = serializers.IntegerField(source='reject_step_count')
    startDate = serializers.DateTimeField(source='start_date', format="%Y-%m-%d %H:%M:%S")
    endDate = serializers.DateTimeField(source='end_date', format="%Y-%m-%d %H:%M:%S")
    expireDay = serializers.IntegerField(source='expire_day')


class WorkflowAllDataStepResponseSerializer(serializers.Serializer):
    step = WorkflowAllDataStepRawResponseSerializer()
    tasks = serializers.ListField(
        child=WorkflowAllDataTaskResponseSerializer()
    )
    comments = serializers.ListField(
        child=WorkflowAllDataCommentResponseSerializer()
    )


class WorkflowAllDataWorkflowResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    accountName = serializers.CharField(allow_null=True, source='account.name')
    accountId = serializers.IntegerField(allow_null=True, source='account.id')
    contractName = serializers.CharField(allow_null=True, source='contract.name')
    contractId = serializers.IntegerField(allow_null=True, source='contract.id')
    renewalFromContract = ContractItemResponseSerializer(allow_null=True, source='renewal_from_contract')
    clientName = serializers.CharField(allow_null=True, source='client.name')
    clientId = serializers.IntegerField(allow_null=True, source='client.id')
    currentStepId = serializers.IntegerField(source='current_step_id')
    workflowType = serializers.IntegerField(source='type')
    isRejected = serializers.BooleanField(source='is_rejected')
    template = RecursiveField(recurse_targets=['template'])
    memo = serializers.CharField()
    status = serializers.IntegerField()
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")
    createdBy = UserResponseSerializerEasy(source='created_by')
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")
    updatedBy = UserResponseSerializerEasy(source='updated_by')

    def __init__(self, *args, **kwargs):
        processed = kwargs.pop('processed', set())
        super().__init__(*args, **kwargs)
        self.processed = processed


class WorkflowAllDataResponseSerializer(serializers.Serializer):
    workflow = WorkflowAllDataWorkflowResponseSerializer()
    steps = serializers.ListField(
        child=WorkflowAllDataStepResponseSerializer()
    )


class WorkflowAllDataResponseBodySerializer(serializers.Serializer):

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
            instanceがシリアライズの対象になる
            """
        self.instance = {"response": data}

    response = serializers.ListField(
        child=WorkflowAllDataResponseSerializer()
    )


class WorkflowsBodySerializer(serializers.Serializer):

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
            instanceがシリアライズの対象になる
            """
        self.instance = {"response": data}

    response = serializers.ListField(
        child=WorkflowAllDataWorkflowResponseSerializer(),
        allow_empty=True,
    )


class WorkflowAllDataStepResponseBodySerializer(serializers.Serializer):
    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
            instanceがシリアライズの対象になる
            """
        self.instance = {"response": data}

    response = WorkflowAllDataStepResponseSerializer()


class WorkflowAddCommentRequestBodySerializer(serializers.Serializer):
    stepId = serializers.IntegerField()
    comment = serializers.CharField(allow_blank=True)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class WorkflowFinishTaskUserRequestBodySerializer(serializers.Serializer):
    taskId = serializers.IntegerField()
    taskUserId = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class WorkflowFinishTaskUserResponseBodySerializer(serializers.Serializer):
    taskFinished = serializers.BooleanField(source='task_finished')
    stepFinished = serializers.BooleanField(source='step_finished')
    workflowFinished = serializers.BooleanField(source='workflow_finished')


class WorkflowRejectRequestBodySerializer(serializers.Serializer):
    stepId = serializers.IntegerField()
    rejectCount = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class WorkflowNotificationResponseSerializer(serializers.Serializer):
    workflowId = serializers.IntegerField()
    stepId = serializers.IntegerField()
    stepStart = serializers.CharField()
    stepLimit = serializers.IntegerField()
    taskId = serializers.IntegerField()
    taskName = serializers.CharField()
    taskType = serializers.IntegerField()
    clientId = serializers.IntegerField(allow_null=True)
    clientName = serializers.CharField(allow_blank=True)
    contractId = serializers.IntegerField(allow_null=True)
    contractName = serializers.CharField(allow_blank=True)


class WorkflowNotificationListResponseBodySerializer(serializers.Serializer):
    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
            instanceがシリアライズの対象になる
            """
        self.instance = {"response": data}

    response = serializers.ListField(
        child=WorkflowNotificationResponseSerializer(),
        allow_empty=True
    )


class WorkflowDeleteRequestBodySerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    workflowType = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class WorkflowAllDataGroupRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    users = UserResponseSerializerEasy(many=True)  # グループに所属しているユーザー


class WorkflowAllDataTaskUserGroupRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    isFinish = serializers.BooleanField()
    user = UserResponseSerializerEasy(allow_null=True)
    group = WorkflowAllDataGroupRequestSerializer(allow_null=True)


class WorkflowAllDataTaskMasterRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    type = serializers.IntegerField()
    isNeedContract = serializers.BooleanField()


class WorkflowAllDataTaskRawRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    isFinish = serializers.BooleanField()
    finishCondition = serializers.IntegerField()
    authorNotify = serializers.IntegerField()
    master = WorkflowAllDataTaskMasterRequestSerializer()


class WorkflowAllDataTaskRequestSerializer(serializers.Serializer):
    task = WorkflowAllDataTaskRawRequestSerializer()
    users = serializers.ListField(
        child=WorkflowAllDataTaskUserGroupRequestSerializer()
    )
    groups = serializers.ListField(
        child=WorkflowAllDataTaskUserGroupRequestSerializer()
    )


class WorkflowAllDataCommentRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    comment = serializers.CharField(allow_blank=True, default="")
    user = UserResponseSerializerEasy()
    # createdAt = serializers.DateTimeField(allow_null=True)
    # updatedAt = serializers.DateTimeField(allow_null=True)


class WorkflowAllDataStepRawRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    memo = serializers.CharField(allow_blank=True, default="")
    parentStepId = serializers.IntegerField(allow_null=True)
    childStepId = serializers.IntegerField(allow_null=True)
    rejectStepCount = serializers.IntegerField()
    # startDate = serializers.DateTimeField(allow_null=True)
    # endDate = serializers.DateTimeField(allow_null=True)
    expireDay = serializers.IntegerField()


class WorkflowAllDataStepRequestSerializer(serializers.Serializer):
    step = WorkflowAllDataStepRawRequestSerializer()
    tasks = serializers.ListField(
        child=WorkflowAllDataTaskRequestSerializer()
    )
    comments = serializers.ListField(
        child=WorkflowAllDataCommentRequestSerializer(),
        allow_empty=True
    )


class WorkflowAllDataWorkflowRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    contractId = serializers.CharField(allow_null=True)
    clientId = serializers.CharField(allow_null=True)
    currentStepId = serializers.IntegerField()
    workflowType = serializers.IntegerField()
    isRejected = serializers.BooleanField()
    memo = serializers.CharField(allow_blank=True, default="")


class WorkflowAllDataRequestSerializer(serializers.Serializer):
    workflow = WorkflowAllDataWorkflowRequestSerializer()
    steps = serializers.ListField(
        child=WorkflowAllDataStepRequestSerializer()
    )


class WorkflowCloneRequestBodySerializer(serializers.Serializer):
    template = WorkflowAllDataRequestSerializer()
    name = serializers.CharField()
    cloneType = serializers.IntegerField()
    renewalContractId = serializers.IntegerField(allow_null=True, default=0)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class WorkflowStartRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    directoryId = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs
