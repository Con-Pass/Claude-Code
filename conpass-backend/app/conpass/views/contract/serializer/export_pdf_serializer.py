from rest_framework import serializers


class ContractExportPdfRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    title = serializers.CharField()
    body = serializers.CharField()
    id = serializers.CharField()
    qr = serializers.BooleanField(default=False)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs
