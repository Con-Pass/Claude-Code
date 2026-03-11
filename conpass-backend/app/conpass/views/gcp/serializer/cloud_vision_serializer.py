from rest_framework import serializers


class GoogleCloudVisionRequestSerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    id: Fileのid
    path: bucket 内のファイルパス
    """
    id = serializers.IntegerField(required=False)
    path = serializers.CharField(required=False)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        if not attrs.get('id') and not attrs.get('path'):
            raise serializers.ValidationError("id と path いずれかが必須です。")

        return attrs
