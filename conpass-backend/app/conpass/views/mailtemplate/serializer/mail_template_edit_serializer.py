from rest_framework import serializers
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class MailTemplateEditGetRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)
    type = serializers.IntegerField(error_messages={'null': '種類が選択されていません。'})

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class MailTemplateEditPostRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)
    templateType = serializers.CharField(error_messages={'blank': '種類が選択されていません。'})
    templateText = serializers.CharField(error_messages={'blank': 'メール本文を入力してください。'})

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class MailTemplateEditResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    templateType = serializers.IntegerField(source='template_type', allow_null=True)
    templateText = serializers.CharField(source='template_text', allow_blank=True)


class MailTemplateEditResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """
    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = MailTemplateEditResponseSerializer()
