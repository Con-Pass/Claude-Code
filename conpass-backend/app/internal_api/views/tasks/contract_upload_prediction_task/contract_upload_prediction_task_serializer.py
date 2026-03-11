from rest_framework import serializers


class PrivateApiExecutePredictionOnUploadTaskRequestBodySerializer(serializers.Serializer):
    predictFileId = serializers.IntegerField()
    predictFileUrl = serializers.CharField()
    contractId = serializers.IntegerField()
    userId = serializers.IntegerField()
    datatype = serializers.IntegerField()
    conpassContractType = serializers.CharField(allow_blank=True)
    isMetaCheck = serializers.BooleanField()
    renewNotify = serializers.BooleanField()
    uploadId = serializers.CharField(allow_null=True)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class PrivateApiExecuteZipUploadTaskRequestBodySerializer(serializers.Serializer):
    zipFilePath = serializers.CharField()
    bucketType = serializers.CharField()
    userId = serializers.IntegerField()
    conpassContractType = serializers.CharField(allow_blank=True)
    directoryId = serializers.IntegerField()
    isProvider = serializers.BooleanField()
    isOpen = serializers.BooleanField()
    description = serializers.CharField(allow_blank=True)
    isMetaCheck = serializers.BooleanField()
    renewNotify = serializers.BooleanField()
    uploadId = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class PrivateApiExecuteClassifyByQrcodePresenceTaskRequestBodySerializer(serializers.Serializer):
    zipUploadId = serializers.CharField()
    pdfUploadId = serializers.CharField()
    userId = serializers.IntegerField()
    conpassContractType = serializers.CharField(allow_blank=True)
    directoryId = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs
