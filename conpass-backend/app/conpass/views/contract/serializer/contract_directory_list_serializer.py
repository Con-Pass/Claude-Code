from rest_framework import serializers


class ContractDirectoryListRequestBodySerializer(serializers.Serializer):
    type = serializers.IntegerField(required=False, allow_null=True)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractDirectoryListResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    level = serializers.IntegerField()
    parentId = serializers.IntegerField(source='parent_id', allow_null=True)
    type = serializers.IntegerField()


class ContractDirectoryListResponseBodySerializer(serializers.Serializer):
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
        child=ContractDirectoryListResponseSerializer(),
        allow_empty=True
    )
