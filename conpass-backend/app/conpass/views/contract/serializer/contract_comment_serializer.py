from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy

from conpass.models import ContractCommentMention


class ContractCommentRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    id = serializers.IntegerField()  # ID
    version = serializers.CharField()
    comment = serializers.CharField(error_messages={'blank': 'コメントを入力してください。'})

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractCommentDeleteRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    contractId = serializers.IntegerField()
    commentId = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class UserRequestSerializer(serializers.Serializer):
    """
    ユーザーの簡略版情報をシリアライズします。
    """
    id = serializers.IntegerField()  # ユーザーID
    name = serializers.CharField(source='username')  # ユーザー名


class ContractMentionRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    id = serializers.IntegerField()  # ID
    version = serializers.CharField()
    comment = serializers.CharField(error_messages={'blank': 'コメントを入力してください。'})
    users = UserRequestSerializer(many=True)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class MentionUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(source='user.id')
    name = serializers.CharField(source='user.username')


class ContractCommentListSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    linkedVersion = serializers.IntegerField(source='linked_version')
    comment = serializers.CharField()  # コメント
    status = serializers.IntegerField()  # ステータス（有効無効）
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者
    mentions = serializers.SerializerMethodField()

    def get_mentions(self, obj):
        mentions = ContractCommentMention.objects.filter(comment_id=obj.id)
        return MentionUserSerializer(mentions, many=True).data
