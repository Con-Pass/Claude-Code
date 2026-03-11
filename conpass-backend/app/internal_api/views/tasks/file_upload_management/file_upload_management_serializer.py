from rest_framework import serializers


class PrivateApiExecuteCheckUploadResultRequestBodySerializer(serializers.Serializer):
    dateString = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class PrivateApiExecuteCleanFailedUploadsRequestBodySerializer(serializers.Serializer):
    dateString = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs
