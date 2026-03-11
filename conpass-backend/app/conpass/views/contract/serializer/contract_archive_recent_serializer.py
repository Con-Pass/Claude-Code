from rest_framework import serializers


class ContractArchiveRecentRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractArchiveRecentResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    bodyText = serializers.CharField(source='body_text')
    createdAt = serializers.DateTimeField(source='created_at', format='%Y-%m-%d')


class ContractArchiveRecentResponseBodySerializer(serializers.Serializer):
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
        child=ContractArchiveRecentResponseSerializer(),
        allow_empty=True
    )
