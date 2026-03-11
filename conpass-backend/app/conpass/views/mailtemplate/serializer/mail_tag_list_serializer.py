from rest_framework import serializers
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class MailTagListRequestBodySerializer(serializers.Serializer):

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class MailTagListResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    tag = serializers.CharField()
    text = serializers.CharField()


class MailTagListResponseBodySerializer(serializers.Serializer):
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
        child=MailTagListResponseSerializer(),
        allow_empty=True
    )
