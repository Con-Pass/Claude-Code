from rest_framework import serializers


class UserRequestBodySerializer(serializers.Serializer):
    userName = serializers.CharField(allow_blank=True, required=False)
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


class UserDeleteRequestBodySerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class UserResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    accountName = serializers.CharField(source='account.name', allow_null=True)  # 顧客名
    accountMfaStatus = serializers.IntegerField(source='account.mfa_status', allow_null=True)  # アカウントの2段階認証ステータス
    username = serializers.CharField()  # 名前
    type = serializers.CharField()  # ロール
    status = serializers.IntegerField()  # ステータス
    mfaStatus = serializers.IntegerField(source='mfa_status', allow_null=False)  # 2段階認証ステータス
    lastLogin = serializers.DateTimeField(source='last_login', format="%Y-%m-%d %H:%M:%S")  # 最終ログイン


class UserResponseBodySerializer(serializers.Serializer):
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
        child=UserResponseSerializer(),
        allow_empty=True
    )
