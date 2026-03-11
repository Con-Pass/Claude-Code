from rest_framework import serializers


class ContractStatusUpdateRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    id = serializers.IntegerField()  # ID

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractStatusUpdateResponseSerializer(serializers.Serializer):
    pass


class ContractStatusUpdateResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = ContractStatusUpdateResponseSerializer()
