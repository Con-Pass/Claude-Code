from rest_framework import serializers
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class MailTemplateListRequestBodySerializer(serializers.Serializer):

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class MailTemplateListResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    templateType = serializers.IntegerField(source='template_type')
    templateText = serializers.CharField(source='template_text')
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者


class MailTemplateListResponseBodySerializer(serializers.Serializer):
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
        child=MailTemplateListResponseSerializer(),
        allow_empty=True
    )
