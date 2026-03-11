from rest_framework import serializers


class SettingMetaKeyDirectorySerializer(serializers.Serializer):
    """
    デフォルト項目・自由項目１行ごとのデータ
    """
    id = serializers.IntegerField()  # ID
    name = serializers.CharField(allow_null=True)  # 名前
    type = serializers.CharField()
    is_visible = serializers.BooleanField()  # 表示可否
    meta_key_directory_id = serializers.IntegerField(allow_null=True)  # ID(meta_key_directory.id)


class SettingDirectoryMetaRequestBodySerializer(serializers.Serializer):
    directoryId = serializers.CharField()
    defaultList = serializers.ListField(
        child=SettingMetaKeyDirectorySerializer(),
        allow_empty=True
    )
    freeList = serializers.ListField(
        child=SettingMetaKeyDirectorySerializer(),
        allow_empty=True
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class SettingDirectoryMetalResponseSerializer(serializers.Serializer):
    default_list = SettingMetaKeyDirectorySerializer(many=True)
    free_list = SettingMetaKeyDirectorySerializer(many=True)


class SettingDirectoryMetaResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = SettingDirectoryMetalResponseSerializer()
