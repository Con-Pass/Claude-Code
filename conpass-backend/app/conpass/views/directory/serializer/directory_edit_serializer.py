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


class SettingDirectoryIdsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class SettingDirectoryChildSerializer(serializers.Serializer):
    """
    デフォルト項目・自由項目１行ごとのデータ
    """
    id = serializers.IntegerField(allow_null=True, required=False)  # ID
    name = serializers.CharField(allow_blank=True, required=False)  # 名前
    type = serializers.IntegerField(allow_null=True, required=False)  # 種別（契約書／テンプレート／過去契約書）
    memo = serializers.CharField(allow_blank=True, required=False)  # 備考
    status = serializers.IntegerField()  # ステータス（有効無効）
    sort_id = serializers.IntegerField(allow_null=True, required=False)  # ID
    users = serializers.ListField(
        child=SettingDirectoryIdsSerializer(),
        allow_empty=True,
        allow_null=True
    )
    groups = serializers.ListField(
        child=SettingDirectoryIdsSerializer(),
        allow_empty=True,
        allow_null=True
    )


class SettingDirectoryRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)
    name = serializers.CharField(error_messages={'blank': 'フォルダ名を入力してください。'})  # 階層名
    type = serializers.IntegerField()  # 種別（契約書／テンプレート／過去契約書）
    sort_id = serializers.IntegerField(allow_null=True, required=False)
    defaultKeyList = serializers.ListField(
        child=SettingMetaKeyDirectorySerializer(),
        allow_empty=True
    )
    freeKeyList = serializers.ListField(
        child=SettingMetaKeyDirectorySerializer(),
        allow_empty=True
    )
    childList = serializers.ListField(
        child=SettingDirectoryChildSerializer(),
        allow_empty=True
    )
    memo = serializers.CharField(allow_blank=True, required=False)  # 備考
    users = serializers.ListField(
        child=SettingDirectoryIdsSerializer(),
        allow_empty=True,
        allow_null=True
    )
    groups = serializers.ListField(
        child=SettingDirectoryIdsSerializer(),
        allow_empty=True,
        allow_null=True
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data
