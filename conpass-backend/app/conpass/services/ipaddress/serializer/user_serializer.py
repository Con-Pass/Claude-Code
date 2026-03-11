from rest_framework import serializers


class UserResponseSerializerEasy(serializers.Serializer):
    """
    IDと名前だけの簡略版
    """
    id = serializers.IntegerField()  # ID
    name = serializers.CharField(source='username')  # 名前


class UserResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    login_name = serializers.CharField()  # ログイン名
    password = serializers.CharField()  # ログインパスワード
    username = serializers.CharField()  # ユーザ名
    division = serializers.CharField()  # 部署名
    position = serializers.CharField()  # 役職
    type = serializers.IntegerField()  # 種別（顧客、取引先、管理側）
    account = serializers.DjangoModelField(verbose_name="Account")
    client = serializers.DjangoModelField(verbose_name="Client")
    corporate = serializers.DjangoModelField(verbose_name="Corporate")
    email = serializers.CharField()  # メールアドレス
    tel = serializers.CharField()  # 電話番号
    memo = serializers.CharField()  # 備考
    status = serializers.IntegerField()  # ステータス（有効無効）
    created_at = serializers.DateTimeField()  # 登録日時
    created_by = UserResponseSerializerEasy(source="created_by")  # 登録者
    updated_at = serializers.DateTimeField()  # 更新日時
    updated_by = UserResponseSerializerEasy(source="updated_by")  # 更新者

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass
