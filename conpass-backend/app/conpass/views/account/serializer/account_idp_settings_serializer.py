from rest_framework import serializers


class AccountIdpSettingsRequestBodySerializer(serializers.Serializer):
    idpEntityId = serializers.CharField()
    singleSignOnUrl = serializers.CharField()
    x509Certificate = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data
