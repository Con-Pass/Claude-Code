from rest_framework import serializers


class GroupEditRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID
    name = serializers.CharField(error_messages={'blank': 'グループ名を入力してください。'})  # グループ名
    description = serializers.CharField(allow_blank=True, required=False)  # コメント
    status = serializers.IntegerField()  # ステータス


class GroupEditRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID
    name = serializers.CharField(error_messages={'blank': 'グループ名を入力してください。'})  # グループ名
    description = serializers.CharField(allow_blank=True, required=False)  # コメント
    status = serializers.IntegerField()  # ステータス
    selectUsers = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        error_messages={'empty': 'メンバーを選択してください。'}
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data
