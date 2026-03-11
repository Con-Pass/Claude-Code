from rest_framework import serializers
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class AccountEditRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField(error_messages={'blank': '名前を入力してください。'})  # 名前
    status = serializers.IntegerField(error_messages={'blank': 'ステータスを入力してください。'})  # ステータス
    plan = serializers.IntegerField(error_messages={'blank': 'プランを入力してください。'})  # プラン
    mfaStatus = serializers.IntegerField(allow_null=False, required=True)  # 2段階認証ステータス
    wfBpoTaskDelegatedStampStatus = serializers.IntegerField(error_messages={'blank': '「ConPass BPO 代理押印」設定を入力してください。'})  # ワークフロータスクの「ConPass BPO 代理押印」設定
    wfBpoTaskDelegatedReceiptStatus = serializers.IntegerField(error_messages={'blank': '「ConPass BPO 代理受取」設定を入力してください。'})  # ワークフロータスクの「ConPass BPO 代理受取」設定
    startDate = serializers.DateField(allow_null=True, required=False)   # 開始日
    cancelDate = serializers.DateField(allow_null=True, required=False)  # 解約日
    ipaddressStatus = serializers.IntegerField(allow_null=False, required=True)  # IPアドレス制限ステータス
    ssoStatus = serializers.IntegerField(allow_null=True, required=False)  # SSOの契約状態
    orgStatus = serializers.IntegerField(allow_null=True, required=False)  # ステータス(編集前保持)
    orgPlan = serializers.IntegerField(allow_null=True, required=False)  # プラン(編集前保持)
    orgStartDate = serializers.DateField(allow_null=True, required=False)    # 開始日(編集前保持)
    orgCancelDate = serializers.DateField(allow_null=True, required=False)   # 解約日(編集前保持)
    orgWfBpoTaskDelegatedStampStatus = serializers.IntegerField(allow_null=True, required=False)   # 「ConPass BPO 代理押印」設定(編集前保持)
    orgWfBpoTaskDelegatedReceiptStatus = serializers.IntegerField(allow_null=True, required=False)   # 「ConPass BPO 代理受取」設定(編集前保持)
    orgSsoStatus = serializers.IntegerField(allow_null=True, required=False)  # SSOの契約状態(編集前保持)
    chatbotAccess = serializers.BooleanField(required=True)
    createdAt = serializers.DateTimeField()
    createdBy = UserResponseSerializerEasy()
    updatedAt = serializers.DateTimeField()
    updatedBy = UserResponseSerializerEasy()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        # 開始日、終了日はなにか値が入っている状態から空欄には出来ない
        if attr.get('orgStartDate') and not attr.get('startDate'):
            raise serializers.ValidationError({'startDate': '開始日は空欄に変更できません'})
        if attr.get('orgCancelDate') and not attr.get('cancelDate'):
            raise serializers.ValidationError({'cancelDate': '解約日は空欄に変更できません'})
        # 開始日が空欄の状態でステータスを「準備中」から「有効」に変更することは出来ない
        if not attr.get('startDate'):
            if attr.get('orgStatus') == 20 and attr.get('status') == 1:
                raise serializers.ValidationError(
                    {'changeStatus': '開始日が空欄の状態でステータスを「準備中」から「有効」に変更できません'})

        return attr


class AccountEditResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 名前
    status = serializers.IntegerField()  # ステータス
    plan = serializers.IntegerField()  # プラン
    mfaStatus = serializers.IntegerField(source='mfa_status', allow_null=False, required=True)  # 2段階認証ステータス
    wfBpoTaskDelegatedStampStatus = serializers.IntegerField(source='wf_bpo_task_delegated_stamp_status')  # ワークフロータスクの「ConPass BPO 代理押印」設定
    wfBpoTaskDelegatedReceiptStatus = serializers.IntegerField(source='wf_bpo_task_delegated_receipt_status')  # ワークフロータスクの「ConPass BPO 代理受取」設定
    startDate = serializers.DateField(source='start_date')  # 開始日
    cancelDate = serializers.DateField(source='cancel_date')  # 解約日
    ipaddressStatus = serializers.IntegerField(source='ipaddress_status', allow_null=False, required=True)  # IPアドレス制限ステータス
    orgStatus = serializers.IntegerField(source='status')  # ステータス(編集前保持)
    orgPlan = serializers.IntegerField(source='plan')  # プラン(編集前保持)
    orgWfBpoTaskDelegatedStampStatus = serializers.IntegerField(source='wf_bpo_task_delegated_stamp_status')   # 「ConPass BPO 代理押印」設定(編集前保持)
    orgWfBpoTaskDelegatedReceiptStatus = serializers.IntegerField(source='wf_bpo_task_delegated_receipt_status')   # 「ConPass BPO 代理受取」設定(編集前保持)
    orgStartDate = serializers.DateField(source='start_date', allow_null=True, required=False)  # 開始日(編集前保持)
    orgCancelDate = serializers.DateField(source='cancel_date', allow_null=True, required=False)  # 解約日(編集前保持)
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")
    createdBy = UserResponseSerializerEasy(source='created_by')
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")
    updatedBy = UserResponseSerializerEasy(source='updated_by')
    orgId = serializers.CharField(source='org_id')  # 組織ID
    ssoStatus = serializers.IntegerField(source='sso_status')  # SSOの契約状態
    orgSsoStatus = serializers.IntegerField(source='sso_status')  # SSOの契約状態(編集前保持)
    chatbotAccess = serializers.BooleanField(source='chatbot_access')


class AccountEditResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = AccountEditResponseSerializer()
