from rest_framework import serializers
from conpass.views.conversation.serializer.conversation_detail_serializer import ConversationDetailResponseSerializer


class ConversationCreateResponseBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID
    contractId = serializers.IntegerField(allow_null=False, required=True)  # 契約書ID
    comment = serializers.CharField(allow_blank=False, required=True,
                                    error_messages={'blank': 'コメントを入力してください。'})  # コメント

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class CommentEditRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID
    contractId = serializers.IntegerField(allow_null=False, required=True)  # 契約書ID
    conversationId = serializers.IntegerField(allow_null=False, required=True)  # スレッドID
    comment = serializers.CharField(allow_blank=False, required=True,
                                    error_messages={'blank': 'コメントを入力してください。'})  # コメント

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class ConversationEditResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = ConversationDetailResponseSerializer()
