from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy
from conpass.views.contract.serializer.contract_item_serializer import ContractItemResponseSerializer
from conpass.views.directory.serializer.directory_serializer import DirectoryResponseSerializer
from conpass.views.file.serializer.file_serializer import FileListSerializer


class ContractBodyItemRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    id = serializers.IntegerField()  # ID
    version = serializers.CharField(required=False)
    body = serializers.CharField(required=False)
    isProvider = serializers.IntegerField(required=False, default=None)
    comment = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractBodyContractSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 契約書名
    type = serializers.IntegerField()  # 種別（通常の契約書、テンプレート、過去契約書）
    account_id = serializers.IntegerField(allow_null=True)
    client_id = serializers.IntegerField(allow_null=True)
    directory = DirectoryResponseSerializer(allow_null=True)
    template_id = serializers.IntegerField(allow_null=True)
    origin_id = serializers.IntegerField(allow_null=True)
    version = serializers.CharField()  # バージョン
    files = FileListSerializer(source='file', many=True, allow_null=True)
    isGarbage = serializers.BooleanField(source='is_garbage')  # ゴミ箱に所属
    isProvider = serializers.BooleanField(source='is_provider')  # 自社のものかどうか
    status = serializers.IntegerField()  # ステータス（有効無効）
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者


class ContractBodyItemResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    contract = ContractBodyContractSerializer()
    version = serializers.CharField()  # バージョン
    isAdopted = serializers.BooleanField(source='is_adopted')  # 採用されているかどうか
    body = serializers.CharField()  # 契約書の本文
    status = serializers.IntegerField()  # ステータス（有効無効）
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者


class ContractBodyItemResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = ContractBodyItemResponseSerializer()


class ContractBodyListRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    id = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractBodyDiffHtmlRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    id = serializers.IntegerField()
    olderVersion = serializers.CharField()
    newerVersion = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractBodyVersionAdoptRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    version = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractBodyHistoryResponseSerializer(serializers.Serializer):
    diff = serializers.CharField()
    body = ContractBodyItemResponseSerializer()


class ContractBodyDiffHtmlResponseSerializer(serializers.Serializer):
    diffData = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractBodyListResponseBodySerializer(serializers.Serializer):
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
        child=ContractBodyHistoryResponseSerializer(),
        allow_empty=True
    )
