from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class ContractArchiveCreateRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    id = serializers.IntegerField()  # id
    dragBody = serializers.CharField(error_messages={'blank': '条文を選択してください。'})  # ドラッグした条文
    reason = serializers.CharField(error_messages={'blank': '修正理由を入力してください。'})  # 修正理由

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractArchiveCreateResponseSerializer(serializers.Serializer):
    pass


class ContractArchiveCreateResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = ContractArchiveCreateResponseSerializer()
