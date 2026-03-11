from rest_framework import serializers


class DirectoryResponseSerializer(serializers.Serializer):

    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 階層名
    type = serializers.IntegerField()  # 種別（契約書／テンプレート／過去契約書）
    level = serializers.IntegerField()  # 階層レベル
    memo = serializers.CharField()  # 備考
    sort_id = serializers.IntegerField()
    parent = serializers.IntegerField(source='parent_id', allow_null=True)
    parentName = serializers.CharField(source='parent.name', allow_null=True)


class DirectoryResponseBodySerializer(serializers.Serializer):
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
        child=DirectoryResponseSerializer(),
        allow_empty=True
    )


class DirectoryChildMenuResponseSerializer(serializers.Serializer):

    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 階層名
    type = serializers.IntegerField()  # 種別（契約書／テンプレート／過去契約書）


class DirectoryMenuResponseSerializer(serializers.Serializer):

    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 階層名
    type = serializers.IntegerField()  # 種別（契約書／テンプレート／過去契約書）
    child = serializers.ListField(
        child=DirectoryChildMenuResponseSerializer(),
        allow_empty=True
    )


class DirectoryMenuResponseBodySerializer(serializers.Serializer):
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
        child=DirectoryMenuResponseSerializer(),
        allow_empty=True
    )


class DirectoryDeleteRequestBodySerializer(serializers.Serializer):
    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data
