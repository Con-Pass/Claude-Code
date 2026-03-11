from rest_framework import serializers


class GroupTypeListSerializer(serializers.Serializer):
    """
    デフォルト項目・自由項目１行ごとのデータ
    """
    id = serializers.IntegerField()  # ID
    name = serializers.CharField(allow_null=True)  # 名前


class GroupViewListResponseSerializer(serializers.Serializer):
    account_list = GroupTypeListSerializer(many=True)
    client_list = GroupTypeListSerializer(many=True)
    corporate_list = GroupTypeListSerializer(many=True)


class GroupViewListResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = GroupViewListResponseSerializer()
