from django.contrib.auth import password_validation
from rest_framework import serializers
from django.core.validators import RegexValidator, validate_email

from conpass.models import User


class AccountCreateRequestBodySerializer(serializers.Serializer):
    name = serializers.CharField(error_messages={'blank': '名前を入力してください。'})  # 名前
    status = serializers.IntegerField(error_messages={'blank': 'ステータスを入力してください。'})  # ステータス
    plan = serializers.IntegerField(error_messages={'blank': 'プランを入力してください。'})  # プラン
    mfaStatus = serializers.IntegerField(allow_null=False, required=True)  # 2段階認証ステータス
    wfBpoTaskDelegatedStampStatus = serializers.IntegerField(error_messages={'blank': '「ConPass BPO 代理押印」設定を入力してください。'})  # ワークフロータスクの「ConPass BPO 代理押印」設定
    wfBpoTaskDelegatedReceiptStatus = serializers.IntegerField(error_messages={'blank': '「ConPass BPO 代理受取」設定を入力してください。'})  # ワークフロータスクの「ConPass BPO 代理受取」設定
    ssoStatus = serializers.IntegerField(error_messages={'blank': 'SSOステータスを入力してください。'})  # SSO契約状態
    startDate = serializers.DateField(allow_null=True, required=False)   # 開始日
    cancelDate = serializers.DateField(allow_null=True, required=False)  # 解約日
    ipaddressStatus = serializers.IntegerField(allow_null=False, required=True)  # IPアドレス制限ステータス
    corporateName = serializers.CharField(allow_blank=True, required=False)  # corporate-名前
    address = serializers.CharField(allow_blank=True, required=False)  # corporate-住所
    executiveName = serializers.CharField(allow_blank=True, required=False)  # corporate-代表者名
    salesName = serializers.CharField(allow_blank=True, required=False)  # corporate-営業担当者名
    service = serializers.CharField(allow_blank=True, required=False)  # corporate-サービス
    url = serializers.CharField(allow_blank=True, required=False)  # corporate-URL
    corporateTel = serializers.CharField(allow_blank=True, required=False)  # corporate-電話番号
    loginName = serializers.CharField(validators=[validate_email],
                                      error_messages={'blank': '利用者のログイン名を入力してください。'})  # user-ログインID
    userName = serializers.CharField(error_messages={'blank': '利用者の名前を入力してください。'})  # user-名前
    password = serializers.CharField(error_messages={'blank': '利用者のパスワードを入力してください。'})  # user-パスワード
    division = serializers.CharField(allow_blank=True, required=False)  # user-部署
    position = serializers.CharField(allow_blank=True, required=False)  # user-役職
    userTel = serializers.CharField(error_messages={'blank': '利用者の電話番号を入力してください。'})  # user-電話番号
    memo = serializers.CharField(error_messages={'blank': '利用者の備考を入力してください。'})  # user-備考
    userMfaStatus = serializers.IntegerField(allow_null=False, required=True)  # ユーザー2段階認証ステータス
    chatbotAccess = serializers.BooleanField(default=False)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        """
        Corporateのいずれかの項目が入力された場合
        登録するためすべて必須項目となる
        """
        if attr['corporateName'] or \
                attr['address'] or \
                attr['executiveName'] or \
                attr['salesName'] or \
                attr['service'] or \
                attr['url'] or \
                attr['corporateTel']:
            if not attr['corporateName']:
                raise serializers.ValidationError({'corporateName': '法人の会社名を入力してください'})
            if not attr['address']:
                raise serializers.ValidationError({'address': '法人の住所を入力してください'})
            if not attr['executiveName']:
                raise serializers.ValidationError({'executiveName': '法人の代表者名を入力してください'})
            if not attr['salesName']:
                raise serializers.ValidationError({'salesName': '法人の営業担当者名を入力してください'})
            if not attr['url']:
                raise serializers.ValidationError({'url': '法人のサイトURLを入力してください'})
            if not attr['corporateTel']:
                raise serializers.ValidationError({'corporateTel': '法人の電話番号を入力してください'})

        user = User()
        user.login_name = attr.get('loginName')
        user.username = attr.get('userName')
        user.division = attr.get('division')
        user.position = attr.get('position')
        user.email = attr.get('loginName')
        user.tel = attr.get('userTel')
        user.memo = attr.get('memo')
        user.mfa_status = attr.get('mfaStatus')
        password_validation.validate_password(attr.get('password'), user)

        return attr


class AccountCreateResponseSerializer(serializers.Serializer):
    pass


class AccountCreateResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = AccountCreateResponseSerializer()
