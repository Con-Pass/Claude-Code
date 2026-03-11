from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class InfoListRequestBodySerializer(serializers.Serializer):
    """
    お知らせ一覧検索パラメータ
    """
    status = serializers.CharField(allow_blank=True, required=False)  # 検索条件-ステータス
    orderByStartAt = serializers.CharField(allow_blank=True, required=False)  # 並び順-開始日時
    orderByOrder = serializers.CharField(allow_blank=True, required=False)  # 並び順-優先順位

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class InfoListResponseSerializer(serializers.Serializer):
    """
    お知らせ一覧検索結果項目
    """
    id = serializers.IntegerField()
    title = serializers.CharField()
    body = serializers.CharField()
    order = serializers.IntegerField()
    status = serializers.IntegerField()
    startAt = serializers.DateTimeField(source='start_at', format='%Y-%m-%d %H:%M:%S')
    endAt = serializers.DateTimeField(source='end_at', format='%Y-%m-%d %H:%M:%S')
    createdAt = serializers.DateTimeField(source='created_at', format='%Y-%m-%d %H:%M:%S')
    createdBy = UserResponseSerializerEasy(source='created_by')


class InfoListResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """
    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListField(child=InfoListResponseSerializer(), allow_empty=True)
