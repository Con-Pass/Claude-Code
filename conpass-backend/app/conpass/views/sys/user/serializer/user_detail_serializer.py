from rest_framework import serializers


class UserDetailRequestBodySerializer(serializers.Serializer):
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


class UserDetailResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    loginName = serializers.CharField(source='login_name')  # ログイン名
    password = serializers.CharField()  # ログインパスワード
    username = serializers.CharField()  # 名前
    division = serializers.CharField()  # 部署
    position = serializers.CharField()  # 役職
    email = serializers.CharField()  # メールアドレス
    tel = serializers.CharField()  # 電話番号
    memo = serializers.CharField()  # 備考
    type = serializers.CharField()  # ロール
    isBpo = serializers.BooleanField(source='is_bpo')  # BPOユーザフラグ
    status = serializers.IntegerField()  # ステータス
    mfaStatus = serializers.IntegerField(source='mfa_status', allow_null=False, required=True)  # 2段階認証ステータス
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    accountId = serializers.IntegerField(source='account_id')  # アカウントID
    accountName = serializers.CharField(source='account.name', allow_null=True, required=False)  # アカウント名
    accountPlan = serializers.IntegerField(source='account.plan', allow_null=True, required=False)  # アカウントプラン
    accountMfaStatus = serializers.IntegerField(source='account.mfa_status', allow_null=True, required=False)  # アカウントの2段階認証ステータス
    clientId = serializers.IntegerField(source='client_id')  # 連絡先ID
    clientName = serializers.CharField(source='client.name', allow_null=True, required=False)  # 連絡先名
    corporateId = serializers.IntegerField(source='corporate_id')  # 法人ID
    corporateName = serializers.CharField(source='corporate.name', allow_null=True, required=False)  # 法人名
    isBpoAdmin = serializers.BooleanField(source='is_bpo_admin')  # BPO契約管理者


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
