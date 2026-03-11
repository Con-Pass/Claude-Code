from rest_framework import serializers
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class SysCorporateRequestBodySerializer(serializers.Serializer):
    corporateName = serializers.CharField(allow_blank=True, required=False)
    """
    request body serializer
    APIのパラメータをバリデートします
    """

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class SysCorporateResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 会社名
    address = serializers.CharField()  # 住所
    executiveName = serializers.CharField(source='executive_name')  # 代表者名
    salesName = serializers.CharField(source='sales_name')  # 営業担当者名
    service = serializers.CharField()  # 商品／サービス名
    url = serializers.CharField()  # サイトURL
    tel = serializers.CharField()  # 電話番号
    status = serializers.IntegerField()  # ステータス（有効無効）


class SysCorporateResponseBodySerializer(serializers.Serializer):
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
        child=SysCorporateResponseSerializer(),
        allow_empty=True
    )


class SysCorporateDeleteRequestBodySerializer(serializers.Serializer):
    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data
