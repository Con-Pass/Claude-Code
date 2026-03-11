from rest_framework import serializers


class SysUploadLoginAdFileRequestSerializer(serializers.Serializer):
    file = serializers.FileField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs
