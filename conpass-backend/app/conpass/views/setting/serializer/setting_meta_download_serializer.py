from rest_framework import serializers


class SettingMetaDownloadRequestSerializer(serializers.Serializer):
    metaKeyIds = serializers.CharField()


class SettingContractMetaDownloadRequestSerializer(serializers.Serializer):
    createDateFrom = serializers.CharField()
    createDateTo = serializers.CharField()
