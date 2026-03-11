from rest_framework import serializers


class BpoCreateRequestBodySerializer(serializers.Serializer):
    name = serializers.CharField(error_messages={'blank': 'BPO依頼件名を入力してください。'})  # BPO依頼件名
    text = serializers.CharField(error_messages={'blank': 'BPO依頼内容を入力してください。'})  # BPO依頼内容
    type = serializers.IntegerField(error_messages={'blank': 'BPO依頼種別を入力してください。',
                                                    'null': 'BPO依頼種別を入力してください。'})  # BPO依頼種別

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class BpoCreateResponseSerializer(serializers.Serializer):
    pass


class BpoCreateResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """
    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = BpoCreateResponseSerializer()


class BpoCorrectionCreateRequestBodySerializer(serializers.Serializer):
    contractIds = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        error_messages={'blank': '契約書IDを入力してください。', 'null': '契約書IDを入力してください。'}
    )  # 契約書ID

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class BpoCorrectionCompleteRequestBodySerializer(serializers.Serializer):
    contractId = serializers.IntegerField()  # 契約書ID

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr
