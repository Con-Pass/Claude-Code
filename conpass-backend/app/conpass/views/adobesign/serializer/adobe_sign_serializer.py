from rest_framework import serializers


class AdobeSignCertificationRequestSerializer(serializers.Serializer):
    applicationId = serializers.CharField()
    clientSecret = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class AdobeSignRequestBodySerializer(serializers.Serializer):
    code = serializers.CharField()
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


class AdobeSignTransientDocumentsFileRequestSerializer(serializers.Serializer):
    filename = serializers.CharField()
    blob = serializers.FileField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs
