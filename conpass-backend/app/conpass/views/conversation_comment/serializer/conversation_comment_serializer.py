from rest_framework import serializers


class CommentDeleteRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class ConversationCommentResponseSerializer(serializers.Serializer):
    uid = serializers.SerializerMethodField()  # ID
    author = serializers.CharField()  # コメント者
    content = serializers.CharField(source='comment')  # 内容
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 登録日時
    modifiedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時

    def get_uid(self, obj):
        return str(obj.id)
