from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class SupportListRequestBodySerializer(serializers.Serializer):
    response = serializers.CharField(allow_blank=True, required=False)  # 検索条件-対応状況

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class SupportListResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    body = serializers.CharField()
    type = serializers.IntegerField()
    response = serializers.IntegerField()
    status = serializers.IntegerField()
    accountName = serializers.CharField(source='created_by.account.name', allow_blank=True, required=False)
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")
    createdBy = UserResponseSerializerEasy(source='created_by')


class SupportListResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """
    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListField(child=SupportListResponseSerializer(), allow_empty=True)
