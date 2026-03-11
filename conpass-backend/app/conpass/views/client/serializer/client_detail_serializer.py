from rest_framework import serializers


class ClientDetailRequestBodySerializer(serializers.Serializer):
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


class ClientDetailResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    corporateName = serializers.CharField(source='corporate.name')  # 会社名
    corporateAddress = serializers.CharField(source='corporate.address')  # 住所
    corporateExecutiveName = serializers.CharField(source='corporate.executive_name')  # 代表者名
    corporateSalesName = serializers.CharField(source='corporate.sales_name')  # 営業担当者名
    createdAt = serializers.DateTimeField(source='created_at', format='%Y-%m-%d %H:%M:%S')  # 登録日時


class ClientDetailResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = ClientDetailResponseSerializer()
