from rest_framework import serializers
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class MailTemplatePreviewRequestBodySerializer(serializers.Serializer):
    body = serializers.CharField(allow_blank=True, required=False)
    client = serializers.CharField(allow_blank=True, required=False)
    concludeDate = serializers.CharField(allow_blank=True, required=False)
    limitDate = serializers.CharField(allow_blank=True, required=False)
    detailUrl = serializers.CharField(allow_blank=True, required=False)
    renewUrl = serializers.CharField(allow_blank=True, required=False)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class MailTemplatePreviewResponseSerializer(serializers.Serializer):
    body = serializers.CharField()


class MailTemplatePreviewResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """
    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = MailTemplatePreviewResponseSerializer()
