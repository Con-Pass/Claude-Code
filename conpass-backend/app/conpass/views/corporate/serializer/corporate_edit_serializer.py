from rest_framework import serializers
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class CorporateEditRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID
    name = serializers.CharField(error_messages={'blank': '会社名を入力してください。'})  # 会社名
    address = serializers.CharField(error_messages={'blank': '住所を入力してください。'})  # 住所
    executiveName = serializers.CharField(error_messages={'blank': '代表者名を入力してください。'})  # 代表者名
    salesName = serializers.CharField(error_messages={'blank': '営業担当者名を入力してください。'})  # 営業担当者名
    service = serializers.CharField(error_messages={'blank': '商品／サービス名を入力してください。'})  # 商品／サービス名
    url = serializers.CharField(error_messages={'blank': 'サイトURLを入力してください。'})  # サイトURL
    tel = serializers.CharField(error_messages={'blank': '電話番号を入力してください。'})  # 電話番号
    status = serializers.IntegerField()  # ステータス（有効無効）

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class CorporateEditSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 会社名
    address = serializers.CharField()  # 住所
    executiveName = serializers.CharField(source='executive_name')  # 代表者名
    salesName = serializers.CharField(source='sales_name')  # 営業担当者名
    service = serializers.CharField()  # 商品／サービス名
    url = serializers.CharField()  # サイトURL
    tel = serializers.CharField()  # 電話番号
    status = serializers.IntegerField()  # ステータス（有効無効）
    createdAt = serializers.DateTimeField(source='created_at', format='%Y-%m-%d %H:%M:%S')  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 作成者
    updatedAt = serializers.DateTimeField(source='updated_at', format='%Y-%m-%d %H:%M:%S')  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者


class CorporateEditResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = CorporateEditSerializer()
