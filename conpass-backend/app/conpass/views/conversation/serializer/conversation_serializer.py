from rest_framework import serializers
from conpass.views.conversation_comment.serializer.conversation_comment_serializer import \
    ConversationCommentResponseSerializer


class ConversationRequestBodySerializer(serializers.Serializer):
    contract_id = serializers.IntegerField()  # ID
    conversation_id = serializers.IntegerField()  # ID

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class ConversationDeleteRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class ConversationDeleteAllRequestBodySerializer(serializers.Serializer):
    contract_id = serializers.IntegerField()  # 契約書ID

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class ConversationFetchRequestBodySerializer(serializers.Serializer):
    body = serializers.CharField()
    contract_id = serializers.IntegerField()  # 契約書ID

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class ConversationResponseSerializer(serializers.Serializer):
    uid = serializers.SerializerMethodField()  # ID
    author = serializers.CharField(source='user.username')  # ユーザー
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 登録日時
    modifiedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    comments = serializers.ListField(
        child=ConversationCommentResponseSerializer(),
        allow_empty=True
    )

    def get_uid(self, obj):
        return str(obj.id)


class ConversationResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = ConversationResponseSerializer()
