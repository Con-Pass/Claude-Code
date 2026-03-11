from rest_framework import serializers


class GroupEditRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID
    name = serializers.CharField(error_messages={'blank': 'グループ名を入力してください。'})  # グループ名
    description = serializers.CharField(allow_blank=True, required=False)  # コメント
    status = serializers.IntegerField()  # ステータス


class GroupEditRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID
    name = serializers.CharField(error_messages={'blank': 'グループ名を入力してください。'})  # グループ名
    description = serializers.CharField(allow_blank=True, required=False)  # コメント
    status = serializers.IntegerField()  # ステータス
    accountId = serializers.IntegerField(error_messages={'blank': 'アカウントを選択してください。',
                                                         'null': 'アカウントを選択してください。'})  # アカウントID
    selectUsers = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        error_messages={'empty': 'メンバーを選択してください。'}
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class GroupAccountListSerializer(serializers.Serializer):
    """
    デフォルト項目・自由項目１行ごとのデータ
    """
    id = serializers.IntegerField()  # ID
    name = serializers.CharField(allow_null=True)  # 名前


class GroupAccountResponseBodySerializer(serializers.Serializer):
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
        child=GroupAccountListSerializer(),
        allow_empty=True
    )
