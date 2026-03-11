from rest_framework import serializers


class AccountRequestBodySerializer(serializers.Serializer):
    name = serializers.CharField(allow_blank=True, required=False)
    plan = serializers.CharField(allow_blank=True, required=False)
    status = serializers.CharField(allow_blank=True, required=False)
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


class AccountDeleteRequestBodySerializer(serializers.Serializer):
    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class AccountResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 名前
    status = serializers.IntegerField()  # ステータス
    plan = serializers.IntegerField()  # プラン
    mfaStatus = serializers.IntegerField(source='mfa_status')  # 2段階認証ステータス
    wfBpoTaskDelegatedStampStatus = serializers.IntegerField(source='wf_bpo_task_delegated_stamp_status')  # ワークフロータスクの「ConPass BPO 代理押印」設定
    wfBpoTaskDelegatedReceiptStatus = serializers.IntegerField(source='wf_bpo_task_delegated_receipt_status')  # ワークフロータスクの「ConPass BPO 代理受取」設定
    startDate = serializers.DateField(source='start_date')  # 開始日
    cancelDate = serializers.DateField(source='cancel_date')  # 解約日
    ipaddressStatus = serializers.IntegerField(source='ipaddress_status')  # IPアドレス制限ステータス
    orgId = serializers.CharField(source='org_id')  # 組織ID
    ssoStatus = serializers.IntegerField(source='sso_status')  # SSOの契約状態
    chatbotAccess= serializers.BooleanField(source='chatbot_access')



class AccountResponseBodySerializer(serializers.Serializer):
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
        child=AccountResponseSerializer(),
        allow_empty=True
    )
