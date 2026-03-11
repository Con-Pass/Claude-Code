from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class SupportDetailRequestBodySerializer(serializers.Serializer):
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


class SupportDetailEditRequestBodySerializer(serializers.Serializer):
    """
    更新処理用(POST)
    """
    id = serializers.IntegerField()  # PK
    status = serializers.IntegerField()  # ステータス
    response = serializers.IntegerField()  # 対応状況

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class SupportDetailResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    body = serializers.CharField()
    type = serializers.IntegerField()
    response = serializers.IntegerField()
    status = serializers.IntegerField()
    accountName = serializers.CharField(source='created_by.account.name', allow_blank=True, required=False)
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")
    createdBy = UserResponseSerializerEasy(source='created_by')
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")
    updatedBy = UserResponseSerializerEasy(source='updated_by')


class SupportDetailResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """
    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = SupportDetailResponseSerializer()
