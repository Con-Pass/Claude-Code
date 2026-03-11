from rest_framework import serializers


class SupportRequestRequestBodySerializer(serializers.Serializer):
    name = serializers.CharField(error_messages={'blank': '問い合わせ件名を入力してください。'})  # 問い合わせ件名
    body = serializers.CharField(error_messages={'blank': '問い合わせ内容を入力してください。'})  # 問い合わせ内容
    type = serializers.IntegerField(error_messages={'blank': '問い合わせ種別を入力してください。',
                                                    'null': '問い合わせ種別を入力してください。'})  # 問い合わせ種別

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class SupportRequestResponseSerializer(serializers.Serializer):
    pass


class SupportRequestResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """
    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = SupportRequestResponseSerializer()
