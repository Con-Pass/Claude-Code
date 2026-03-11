from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class WorkflowAllDataUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.IntegerField()


class WorkflowAllDataGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    users = serializers.ListField(
        child=WorkflowAllDataUserSerializer()
    )


class WorkflowAllDataTaskUserUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    is_finish = serializers.BooleanField()
    user = WorkflowAllDataUserSerializer()


class WorkflowAllDataTaskGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    is_finish = serializers.BooleanField()
    group = WorkflowAllDataGroupSerializer()


class WorkflowAllDataTaskSerializer(serializers.Serializer):
    name = serializers.CharField(source='data.name')
    finish_condition = serializers.IntegerField(source='data.finish_condition')
    users = serializers.ListField(
        child=WorkflowAllDataTaskUserUserSerializer(),
        allow_empty=True,
        allow_null=True
    )
    groups = serializers.ListField(
        child=WorkflowAllDataTaskGroupSerializer(),
        allow_empty=True,
        allow_null=True
    )


class WorkflowAllDataStepCommentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    comment = serializers.CharField()
    user = UserResponseSerializerEasy()
    created_at = serializers.DateTimeField()  # 登録日時
    updated_at = serializers.DateTimeField()  # 更新日時


class WorkflowAllDataStepSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    parent_step_id = serializers.IntegerField(allow_null=True)
    child_step_id = serializers.IntegerField(allow_null=True)
    memo = serializers.CharField(allow_blank=True)
    reject_step_count = serializers.IntegerField()
    start_date = serializers.DateTimeField(allow_null=True)
    expire_day = serializers.IntegerField()
    comments = serializers.ListField(
        child=WorkflowAllDataStepCommentSerializer(),
        allow_empty=True,
        allow_null=True
    )
    tasks = serializers.ListField(
        child=WorkflowAllDataTaskSerializer(),
        allow_empty=True
    )


class WorkflowAllDataWorkflowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.IntegerField()
    account_name = serializers.CharField(allow_blank=True)
    contract_id = serializers.IntegerField(allow_null=True)
    contract_name = serializers.CharField(allow_blank=True)
    client_id = serializers.IntegerField(allow_null=True)
    client_name = serializers.CharField(allow_blank=True)
    current_step_id = serializers.IntegerField()
    is_rejected = serializers.BooleanField()
    memo = serializers.CharField(allow_blank=True)
    steps = serializers.ListField(
        child=WorkflowAllDataStepSerializer(),
        allow_empty=True
    )


class WorkflowAllDataResponseSerializer(serializers.Serializer):
    result = serializers.ListField(
        child=WorkflowAllDataWorkflowSerializer(),
        allow_empty=True
    )
