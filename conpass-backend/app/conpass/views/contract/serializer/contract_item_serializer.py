from rest_framework import serializers

from conpass.views.common.recursive_field import RecursiveField
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy
from conpass.views.client.serializer.client_detail_serializer import ClientDetailResponseSerializer
from conpass.views.contract.serializer.contract_lease_serializer import ContractLeaseNameSerializer
from conpass.views.directory.serializer.directory_serializer import DirectoryResponseSerializer
from conpass.views.file.serializer.file_serializer import FileListSerializer
from conpass.views.contract.serializer.contract_comment_serializer import ContractCommentListSerializer
from conpass.views.sys.account.serializer.account_serializer import AccountResponseSerializer


class ContractItemRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    id = serializers.IntegerField()  # ID
    type = serializers.IntegerField(allow_null=True, required=False)  # 種別
    directory_id = serializers.IntegerField(allow_null=True, required=False)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractMetaDataRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=False, required=False)
    key_id = serializers.IntegerField(allow_null=False, required=False)
    value = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    dateValue = serializers.DateField(allow_null=True, required=False)
    lock = serializers.BooleanField(allow_null=False, required=False)
    status = serializers.IntegerField(allow_null=False, required=False)

    def validate(self, attrs):
        if attrs.get('id') and attrs.get('key_id'):
            raise serializers.ValidationError('Only one of `id` and `key_id` can be specified')
        return attrs


class ContractMetaDataListRequestBodySerializer(serializers.Serializer):
    list = serializers.ListField(
        child=ContractMetaDataRequestSerializer(),
        required="true"
    )


class ContractItemResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 契約書名
    type = serializers.IntegerField()  # 種別（通常の契約書、テンプレート、過去契約書）
    account = AccountResponseSerializer()
    client = ClientDetailResponseSerializer(allow_null=True)  # 契約先相手
    directory = DirectoryResponseSerializer(allow_null=True)
    template = RecursiveField(allow_null=True, recurse_targets=['template', 'origin', 'parent'])
    origin = RecursiveField(allow_null=True, recurse_targets=['template', 'origin', 'parent'])
    parent = RecursiveField(allow_null=True, recurse_targets=['template', 'origin', 'parent'])
    version = serializers.CharField()  # バージョン
    files = FileListSerializer(source='file', many=True, allow_null=True)
    isGarbage = serializers.BooleanField(source='is_garbage')  # ゴミ箱に所属
    isProvider = serializers.BooleanField(source='is_provider')  # 自社のものかどうか
    isNewLease=serializers.BooleanField(source='is_new_lease', read_only=True)
    leaseKeys=ContractLeaseNameSerializer(source='lease_key', many=True, read_only=True)
    status = serializers.IntegerField()  # ステータス（有効無効）
    isOpen = serializers.BooleanField(source='is_open')
    comments = serializers.ListField(source='get_comments', child=ContractCommentListSerializer(), allow_empty=True)  # コメントの取得
    bpoCorrectionResponse = serializers.IntegerField(source='get_bpo_correction_response')  # BPOデータ補正 対応状況 CorrectionRequestから取る
    bulkZipPath = serializers.CharField(source='bulk_zip_path')
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者

    def __init__(self, *args, **kwargs):
        processed = kwargs.pop('processed', set())
        super().__init__(*args, **kwargs)
        self.processed = processed


class ContractItemResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = ContractItemResponseSerializer()


class ContractMetaDataKeyResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    label = serializers.CharField()
    type = serializers.IntegerField()
    isVisible = serializers.BooleanField(source="is_visible")


class ContractMetaDataResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    key = ContractMetaDataKeyResponseSerializer()
    check = serializers.BooleanField()
    checkedBy = UserResponseSerializerEasy(source='checked_by')
    value = serializers.CharField()
    dateValue = serializers.DateField(source='date_value')
    score = serializers.FloatField()
    startOffset = serializers.IntegerField(source='start_offset')
    endOffset = serializers.IntegerField(source='end_offset')
    status = serializers.IntegerField()
    lock = serializers.BooleanField()
    createdAt = serializers.DateTimeField(source='created_at')
    createdBy = UserResponseSerializerEasy(source='created_by')
    updatedAt = serializers.DateTimeField(source='updated_at')
    updatedBy = UserResponseSerializerEasy(source='updated_by')


class ContractMetaDataResponseBodySerializer(serializers.Serializer):
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
        child=ContractMetaDataResponseSerializer(),
        allow_empty=True
    )


class ContractChildsRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    parentId = serializers.IntegerField()  # ID

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractChildsResponseBodySerializer(serializers.Serializer):
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
        child=ContractItemResponseSerializer(),
        allow_empty=True
    )
