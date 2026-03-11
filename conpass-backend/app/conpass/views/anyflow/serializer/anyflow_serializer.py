from rest_framework import serializers

from conpass.models import Account


class UserIDResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    username = serializers.CharField()  # 名前
    account_id = serializers.IntegerField()
    account_name = serializers.SerializerMethodField()

    def get_account_name(self, obj):
        account_id = obj.account_id
        account_name = Account.objects.get(id=account_id)
        return account_name.name


class UserIDResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = data

    def to_representation(self, instance):
        return UserIDResponseSerializer(instance).data
