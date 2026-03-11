from rest_framework import serializers


class DirectoryDetailRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()
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


class DirectoryDetailUserGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class DirectoryDetailResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 名前
    type = serializers.IntegerField()  # 種別（契約書／テンプレート／過去契約書）
    memo = serializers.CharField()  # 備考
    status = serializers.IntegerField()  # ステータス（有効無効）
    sort_id = serializers.IntegerField()
    groups = serializers.ListField(
        child=DirectoryDetailUserGroupSerializer(),
        allow_empty=True,
    )  # グループID
    users = serializers.ListField(
        child=DirectoryDetailUserGroupSerializer(),
        allow_empty=True,
    )  # ユーザーID


class DirectoryDetailResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = DirectoryDetailResponseSerializer()


class DirectoryChildDetailResponseBodySerializer(serializers.Serializer):
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
        child=DirectoryDetailResponseSerializer(),
        allow_empty=True
    )


class DirectorySortIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)
    sort_id = serializers.IntegerField(allow_null=True, required=False)


class DirectorySortRequestSerializer(serializers.Serializer):
    params = serializers.ListField(
        child=DirectorySortIdSerializer(),
        allow_empty=True
    )
