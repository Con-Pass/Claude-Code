from rest_framework import serializers


class UploadContractFileRequestSerializer(serializers.Serializer):
    filename = serializers.CharField()
    blob = serializers.FileField()
    description = serializers.CharField(required=False, default="")
    datatype = serializers.IntegerField()
    conpassContractType = serializers.CharField(default="")
    directoryId = serializers.CharField(error_messages={'blank': 'フォルダを選択してください'})
    renewNotify = serializers.IntegerField(required=False, default=0)
    isProvider = serializers.IntegerField(required=False, default=0)
    isMetaCheck = serializers.IntegerField(required=False, default=0)
    isOpen = serializers.IntegerField(required=False, default=0)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        if attrs.get('directoryId') == "0":
            raise serializers.ValidationError({'blank': 'フォルダを選択してください'})
        return attrs


class UploadFileLinkedContractRequestSerializer(serializers.Serializer):
    filename = serializers.CharField()
    blob = serializers.FileField()
    description = serializers.CharField(required=False, default="")
    contractId = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class UploadContractUrlRequestSerializer(serializers.Serializer):
    filename = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, default="")
    datatype = serializers.IntegerField()
    directoryId = serializers.CharField(error_messages={'blank': 'フォルダを選択してください'})
    conpassContractType = serializers.CharField(required=False, allow_blank=True, default="")
    renewNotify = serializers.IntegerField(required=False, default=0)
    isProvider = serializers.IntegerField(required=False, default=0)
    isMetaCheck = serializers.IntegerField(required=False, default=0)
    isOpen = serializers.IntegerField(required=False, default=0)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        if attrs.get('directoryId') == "0":
            raise serializers.ValidationError({'blank': 'フォルダを選択してください'})
        return attrs


class NotifyUploadedToGcsRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    filePath = serializers.CharField(allow_blank=True, default='')
    zipPath = serializers.CharField(allow_blank=True, default='')
    size = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs
