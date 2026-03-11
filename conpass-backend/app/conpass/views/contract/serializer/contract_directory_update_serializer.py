from rest_framework import serializers


class ContractDirectoryUpdateRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    directoryId = serializers.CharField(error_messages={'blank': 'フォルダを選択してください'})
    idList = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        error_messages={'empty': '契約書を選択してください'}
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractDirectoryUpdateResponseSerializer(serializers.Serializer):
    pass


class ContractDirectoryUpdateResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = ContractDirectoryUpdateResponseSerializer()
