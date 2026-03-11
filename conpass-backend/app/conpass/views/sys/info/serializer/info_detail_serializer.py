from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class InfoDetailRequestBodySerializer(serializers.Serializer):
    """
    表示用(GET)
    """
    id = serializers.IntegerField()  # PK

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class InfoDetailResponseSerializer(serializers.Serializer):
    """
    お知らせ詳細表示項目
    """
    id = serializers.IntegerField()
    title = serializers.CharField()
    body = serializers.CharField()
    url = serializers.CharField()
    order = serializers.IntegerField()
    status = serializers.IntegerField()
    startAt = serializers.DateTimeField(source='start_at', format='%Y-%m-%d %H:%M:%S')
    endAt = serializers.DateTimeField(source='end_at', format='%Y-%m-%d %H:%M:%S')
    createdAt = serializers.DateTimeField(source='created_at', format='%Y-%m-%d %H:%M:%S')
    createdBy = UserResponseSerializerEasy(source='created_by')
    updatedAt = serializers.DateTimeField(source='updated_at', format='%Y-%m-%d %H:%M:%S')
    updatedBy = UserResponseSerializerEasy(source='updated_by')


class InfoDetailResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """
    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = InfoDetailResponseSerializer()
