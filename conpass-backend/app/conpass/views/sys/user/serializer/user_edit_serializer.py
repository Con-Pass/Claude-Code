from django.contrib.auth import password_validation
from rest_framework import serializers

from conpass.models import User
from conpass.views.sys.user.serializer.user_detail_serializer import UserDetailResponseSerializer


class UserEditRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID
    loginName = serializers.CharField(error_messages={'blank': 'メールアドレスを入力してください。'})  # ログイン名
    password = serializers.CharField(allow_blank=True, required=False)  # ログインパスワード
    inputPassword = serializers.CharField(allow_blank=True, required=False)  # ログインパスワード(入力用)
    username = serializers.CharField(error_messages={'blank': '名前を入力してください。'})  # 名前
    division = serializers.CharField(allow_blank=True, required=False)  # 部署
    position = serializers.CharField(allow_blank=True, required=False)  # 役職
    email = serializers.CharField(allow_blank=True, required=False)  # メールアドレス
    tel = serializers.CharField(allow_blank=True, required=False)  # 電話番号
    memo = serializers.CharField(allow_blank=True, required=False)  # 備考
    status = serializers.IntegerField()  # ステータス
    mfaStatus = serializers.IntegerField(allow_null=False, required=True)  # 2段階認証ステータス
    type = serializers.IntegerField()  # ロール
    isBpo = serializers.BooleanField(default=False, required=False)  # BPOユーザ
    accountId = serializers.IntegerField(allow_null=True, required=False)  # アカウントID
    clientId = serializers.IntegerField(allow_null=True, required=False)  # 連絡先ID
    corporateId = serializers.IntegerField(allow_null=True, required=False)  # 法人ID
    isBpoAdmin = serializers.BooleanField(allow_null=True, required=False)  # BPO契約管理者

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate_password(self, value):
        if not self.initial_data.get('inputPassword'):
            return value
        try:
            user = User.objects.get(pk=self.initial_data.get('id'))
        except User.DoesNotExist:
            user = User()
        user.login_name = self.initial_data.get('loginName') or user.login_name
        user.username = self.initial_data.get('username') or user.username
        user.division = self.initial_data.get('division') or user.division
        user.position = self.initial_data.get('position') or user.position
        user.email = self.initial_data.get('email') or user.email
        user.tel = self.initial_data.get('tel') or user.tel
        user.memo = self.initial_data.get('memo') or user.memo
        user.mfa_status = self.initial_data.get('mfaStatus') or user.mfa_status
        password_validation.validate_password(self.initial_data.get('inputPassword'), user)
        return value


class UserEditResponseBodySerializer(serializers.Serializer):
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
