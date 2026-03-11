from rest_framework import serializers


class SettingDirectoryRequestBodySerializer(serializers.Serializer):
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


class SettingDirectorylResponseSerializer(serializers.Serializer):
    """
    対象ディレクトリ
    """
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 名前


class SettingDirectoryResponseBodySerializer(serializers.Serializer):
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
        child=SettingDirectorylResponseSerializer(),
        allow_empty=True
    )
