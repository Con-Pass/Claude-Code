from rest_framework import serializers


class PrivateApiExecuteAddRequestBodySerializer(serializers.Serializer):
    x = serializers.IntegerField()
    y = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class PrivateApiExecuteVisionScanPdfTaskRequestBodySerializer(serializers.Serializer):
    filename = serializers.CharField()
    contractId = serializers.IntegerField()
    userId = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class PrivateApiExecutePredictionTaskRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    url = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs
