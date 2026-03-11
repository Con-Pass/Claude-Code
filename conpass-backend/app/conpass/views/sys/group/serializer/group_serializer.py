from rest_framework import serializers


class GroupRequestBodySerializer(serializers.Serializer):
    groupName = serializers.CharField(allow_blank=True, required=False)
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


class GroupDeleteRequestBodySerializer(serializers.Serializer):
    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class GroupResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # グループ名
    description = serializers.CharField()  # コメント
    status = serializers.IntegerField()  # ステータス
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時


class GroupResponseBodySerializer(serializers.Serializer):
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
        child=GroupResponseSerializer(),
        allow_empty=True
    )


class GroupUserResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    username = serializers.CharField()  # 名前
    accountId = serializers.IntegerField(source='account_id')  # アカウント


class GroupUserResponseBodySerializer(serializers.Serializer):
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
        child=GroupUserResponseSerializer(),
        allow_empty=True
    )
