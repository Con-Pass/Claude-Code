from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy
from conpass.models import MetaKey
from conpass.views.client.serializer.client_detail_serializer import ClientDetailResponseSerializer
from conpass.views.contract.serializer.contract_item_serializer import ContractItemResponseSerializer
from conpass.views.file.serializer.file_serializer import FileListSerializer
from conpass.views.sys.account.serializer.account_serializer import AccountResponseSerializer


class ContractDataListRequestBodySerializer(serializers.Serializer):
    status = serializers.IntegerField(allow_null=True, required=False)
    name = serializers.CharField(allow_blank=True, required=False)
    account = serializers.IntegerField(allow_null=True, required=False)
    client = serializers.IntegerField(allow_null=True, required=False)
    contractType = serializers.IntegerField(allow_null=True, required=False)
    directory = serializers.IntegerField(allow_null=True, required=False)
    template = serializers.IntegerField(allow_null=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # メタ情報の検索条件は可変のため項目を動的に設定
        for key in self.initial_data.keys():
            if key.startswith('default'):
                self.fields[key] = serializers.CharField(required=False)
            if key.startswith('defaultDate'):
                self.fields[key] = serializers.DateField(allow_null=True, required=False)
            if key.startswith('free'):
                self.fields[key] = serializers.CharField(required=False)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


# 暫定：階層
class DirectoryResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 階層名
    level = serializers.IntegerField()  # 階層レベル
    type = serializers.IntegerField()  # 階層種別


class ContractDataListResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 契約書名
    account = AccountResponseSerializer()
    client = ClientDetailResponseSerializer(allow_null=True)  # 契約先相手
    directory = DirectoryResponseSerializer(allow_null=True)
    template = ContractItemResponseSerializer(allow_null=True)
    origin = ContractItemResponseSerializer(allow_null=True)
    version = serializers.CharField()  # バージョン
    files = FileListSerializer(many=True, allow_null=True)
    status = serializers.IntegerField()  # ステータス（有効無効）
    createdAt = serializers.DateTimeField(source='created_at')  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at')  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者


class ContractDataListResponseBodySerializer(serializers.Serializer):
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
        child=ContractDataListResponseSerializer(),
        allow_empty=True
    )
