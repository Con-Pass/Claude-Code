from rest_framework import serializers


class UserTypeListSerializer(serializers.Serializer):
    """
    デフォルト項目・自由項目１行ごとのデータ
    """
    id = serializers.IntegerField()  # ID
    name = serializers.CharField(allow_null=True)  # 名前
    plan = serializers.IntegerField(allow_null=False, required=False)  # アカウントプラン


class UserViewListResponseSerializer(serializers.Serializer):
    account_list = UserTypeListSerializer(many=True)
    client_list = UserTypeListSerializer(many=True)
    corporate_list = UserTypeListSerializer(many=True)


class UserViewListResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = UserViewListResponseSerializer()
