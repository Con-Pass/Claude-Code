from rest_framework import serializers


class IpAddressRequestBodySerializer(serializers.Serializer):
    ipAddress = serializers.CharField(allow_blank=True, required=False)
    remarks = serializers.CharField(allow_blank=True, required=False)

    """
    request body serializer
    APIのパラメータをバリデートします
    """

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class IpAddressResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    ip_address = serializers.CharField()  # IPアドレス
    remarks = serializers.CharField()  # 備考
    status = serializers.IntegerField()  # ステータス


class IpAddressResponseBodySerializer(serializers.Serializer):
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
        child=IpAddressResponseSerializer(),
        allow_empty=True
    )


class IpAddressDeleteRequestBodySerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data
