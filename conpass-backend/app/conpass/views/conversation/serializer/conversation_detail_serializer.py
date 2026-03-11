from rest_framework import serializers
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class ConversationDetailResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    user = UserResponseSerializerEasy(source='user')  # ユーザー
    createdAt = serializers.DateTimeField(source='conversation.created_at', format="%Y-%m-%d %H:%M:%S")  # 登録日時
    updatedAt = serializers.DateTimeField(source='conversation.updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    conversationCommentId = serializers.IntegerField(source='conversation.conversation_comment.id')  # ID
    conversationCommentUsername = serializers.CharField(source='conversation.conversation_comment.user.username')  # ユーザー名
    conversationCommentComment = serializers.CharField(source='conversation.conversation_comment.comment')  # コメント
    conversationCommentCreatedAt = serializers.DateTimeField(source='conversation.conversation_comment.created_at',
                                                             format="%Y-%m-%d %H:%M:%S")  # 登録日時
    conversationCommentUpdatedAt = serializers.DateTimeField(source='conversation.conversation_comment.updated_at',
                                                             format="%Y-%m-%d %H:%M:%S")  # 更新日時


class ConversationDetailResponseBodySerializer(serializers.Serializer):
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
