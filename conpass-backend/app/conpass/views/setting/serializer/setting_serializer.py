from rest_framework import serializers


class SettingMetaSerializer(serializers.Serializer):
    """
    デフォルト項目・自由項目１行ごとのデータ
    """
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 名前
    type = serializers.IntegerField()  # 種別（デフォルト／自由）
    is_visible = serializers.BooleanField()  # 表示（true/false）
    status = serializers.IntegerField()  # ステータス（有効無効）


class SettingRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """

    settingMeta = serializers.ListField(
        child=SettingMetaSerializer(),
        allow_empty=True
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class SettingResponseSerializer(serializers.Serializer):

    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 項目名
    type = serializers.IntegerField()  # 種別（デフォルト／自由）
    is_visible = serializers.BooleanField()  # 表示（true/false）
    status = serializers.IntegerField()  # ステータス（有効無効）
    createdAt = serializers.DateTimeField(source='created_at')  # 登録日時
    createdById = serializers.IntegerField(source='created_by_id')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at')  # 更新日時
    updatedById = serializers.IntegerField(source='updated_by_id')  # 更新者
    accountId = serializers.IntegerField(source='account_id')  # アカウントID
    label = serializers.CharField()


class SettingResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListField(
        child=SettingResponseSerializer(),
        allow_empty=True
    )


class SettingMetaCSVSerializer(serializers.Serializer):
    """
    項目１行ごとのCSVデータ
    """
    contractId = serializers.IntegerField()  # 契約書ID
    metakeyId = serializers.IntegerField()  # メタキーID
    metadataId = serializers.IntegerField()  # メタデータID
    keyName = serializers.CharField(source='key.name')  # 項目名
    value = serializers.CharField(allow_blank=True)  # 値
    dateValue = serializers.CharField(allow_blank=True)  # 値（日付）


class SettingRequestCSVBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """

    csvSettingMeta = serializers.ListField(
        child=SettingMetaCSVSerializer(),
        allow_empty=True
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data
