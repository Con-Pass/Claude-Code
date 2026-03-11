from rest_framework import serializers


class GroupDetailRequestBodySerializer(serializers.Serializer):
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


class GroupAccountListSerializer(serializers.Serializer):
    """
    デフォルト項目・自由項目１行ごとのデータ
    """
    id = serializers.IntegerField()  # ID
    name = serializers.CharField(allow_null=True)  # 名前


class GroupUserListSerializer(serializers.Serializer):
    """
    デフォルト項目・自由項目１行ごとのデータ
    """
    id = serializers.IntegerField()  # ID
    name = serializers.CharField(source='username', allow_null=True)  # 名前


class GroupDetailResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 名前
    description = serializers.CharField()  # ロール
    account = GroupAccountListSerializer()  # 顧客ID
    status = serializers.IntegerField()  # ステータス
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 作成日時
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    userGroup = GroupUserListSerializer(source='user_group', many=True)  # グループに所属しているユーザー


class GroupDetailResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = GroupDetailResponseSerializer()
