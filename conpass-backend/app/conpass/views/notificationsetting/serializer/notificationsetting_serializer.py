from rest_framework import serializers


class NotificationSettingRequestSerializer(serializers.Serializer):
    type = serializers.IntegerField()
    name = serializers.CharField()
    info = serializers.BooleanField()
    mail = serializers.BooleanField()


class NotificationSettingRequestBodySerializer(serializers.Serializer):
    notificationSettingData = serializers.ListField(
        child=NotificationSettingRequestSerializer(),
        allow_empty=True
    )
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


class NotificationSettingResponseSerializer(serializers.Serializer):
    type = serializers.IntegerField()
    name = serializers.CharField()
    info = serializers.BooleanField()
    mail = serializers.BooleanField()


class NotificationSettingResponseBodySerializer(serializers.Serializer):
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
        child=NotificationSettingResponseSerializer(),
        allow_empty=True
    )
