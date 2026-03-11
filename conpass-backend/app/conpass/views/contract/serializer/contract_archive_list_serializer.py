from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class ContractArchiveListRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    id = serializers.IntegerField()
    searchParamsTemplateName = serializers.CharField(allow_blank=True, required=False)  # テンプレート名
    searchParamsContractBody = serializers.CharField(allow_blank=True, required=False)  # 条文

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


# class ContractArchiveListResponseSerializer(serializers.Serializer):
#     id = serializers.IntegerField()
#     templateName = serializers.CharField(source='contract.template.name')
#     bodyText = serializers.CharField(source='body_text')
#     reason = serializers.CharField()
#     createdBy = UserResponseSerializerEasy(source='created_by')

class ContractArchiveListResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    templateName = serializers.SerializerMethodField()
    bodyText = serializers.CharField(source='body_text')
    reason = serializers.CharField()
    createdBy = UserResponseSerializerEasy(source='created_by')
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    contractName = serializers.SerializerMethodField()

    def get_templateName(self, obj):
        # contract.templateが存在し、かつnameがNoneでない場合はその値を返す
        if obj.contract.template and obj.contract.template.name:
            return obj.contract.template.name
        # それ以外の場合は「テンプレートなし」を返す
        return ''

    def get_contractName(self, obj):
        return obj.contract.name


class ContractArchiveListResponseBodySerializer(serializers.Serializer):
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
        child=ContractArchiveListResponseSerializer(),
        allow_empty=True
    )
