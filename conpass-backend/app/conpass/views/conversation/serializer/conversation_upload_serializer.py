from rest_framework import serializers


class UploadWordFileRequestSerializer(serializers.Serializer):
    contract_id = serializers.CharField()  # ID
    blob = serializers.FileField()
    new_version = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data
