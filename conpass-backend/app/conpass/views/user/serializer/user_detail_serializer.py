from rest_framework import serializers
from conpass.models import PermissionCategoryKey


class UserDetailRequestBodySerializer(serializers.Serializer):
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


class UserDetailResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    accountName = serializers.CharField(source='account.name', required=False, allow_null=True)  # 顧客名
    accountMfaStatus = serializers.IntegerField(source='account.mfa_status', required=False, allow_null=True)  # アカウントの2段階認証ステータス
    loginName = serializers.CharField(source='login_name')  # ログイン名
    password = serializers.CharField()  # ログインパスワード
    username = serializers.CharField()  # 名前
    division = serializers.CharField()  # 部署
    position = serializers.CharField()  # 役職
    email = serializers.CharField()  # メールアドレス
    tel = serializers.CharField()  # 電話番号
    memo = serializers.CharField()  # 備考
    dateJoined = serializers.DateTimeField(source='date_joined', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    lastLogin = serializers.DateTimeField(source='last_login', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    type = serializers.CharField()  # ロール
    status = serializers.IntegerField()  # ステータス
    mfaStatus = serializers.IntegerField(source='mfa_status', allow_null=False, required=True)  # 2段階認証ステータス
    otpSecretUri = serializers.CharField()  # ワンタイムパスワード生成用URI
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    permission_category_id = serializers.SerializerMethodField()
    permission_category_name = serializers.SerializerMethodField()

    def get_permission_category_id(self, obj):
        return obj.permission_category_id

    def get_permission_category_name(self, obj):
        permission_category_id = obj.permission_category_id
        try:
            if permission_category_id is not None:
                permission_category_key = PermissionCategoryKey.objects.get(id=permission_category_id)
                return permission_category_key.name
            else:
                return "カスタム"
        except PermissionCategoryKey.DoesNotExist:
            return "カスタム"


class UserDetailResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = UserDetailResponseSerializer()
