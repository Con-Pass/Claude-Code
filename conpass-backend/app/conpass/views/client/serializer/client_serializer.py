from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy
from conpass.views.sys.account.serializer.account_serializer import AccountResponseSerializer


class ClientRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class ClientDeleteRequestBodySerializer(serializers.Serializer):
    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class ClientResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()
    corporateName = serializers.CharField(source='corporate.name')  # 会社名
    corporateAddress = serializers.CharField(source='corporate.address')  # 住所
    corporateExecutiveName = serializers.CharField(source='corporate.executive_name')  # 代表者名
    corporateSalesName = serializers.CharField(source='corporate.sales_name')  # 営業担当者名 （担当グループ名）
    corporateService = serializers.CharField(source='corporate.service')  # 商品／サービス名
    createdAt = serializers.DateTimeField(source='created_at')  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at')  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者

    # isChecked = serializers.SerializerMethodField()

    def get_isChecked(self, obj):
        '''
            チェックボックスの初期値を返す
        '''
        return False


class ClientResponseBodySerializer(serializers.Serializer):
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
        child=ClientResponseSerializer(),
        allow_empty=True
    )


class ClientDataRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    clientName = serializers.CharField(allow_blank=True, required=False)
    corporateName = serializers.CharField(allow_blank=True, required=False)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class ClientDataResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 連絡先名（契約名）
    providerAccount = AccountResponseSerializer(source='provider_account')
    corporateName = serializers.CharField(source='corporate.name')  # 会社名
    corporateAddress = serializers.CharField(source='corporate.address')  # 住所
    corporateExecutiveName = serializers.CharField(source='corporate.executive_name')  # 代表者名
    corporateSalesName = serializers.CharField(source='corporate.sales_name')  # 営業担当者名 （担当グループ名）
    corporateService = serializers.CharField(source='corporate.service')  # 商品／サービス名
    createdAt = serializers.DateTimeField(source='created_at')  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at')  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者


class ClientDataResponseBodySerializer(serializers.Serializer):
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
        child=ClientDataResponseSerializer(),
        allow_empty=True
    )
