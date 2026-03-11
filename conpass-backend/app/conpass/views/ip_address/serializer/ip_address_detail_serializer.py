from rest_framework import serializers
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class IpAddressDetailRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    id = serializers.IntegerField()  # ID

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class IpAddressDetailResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    ip_address = serializers.CharField()  # IPアドレス
    remarks = serializers.CharField()  # 備考
    status = serializers.IntegerField()  # ステータス
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者


class IpAddressDetailResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = IpAddressDetailResponseSerializer()
