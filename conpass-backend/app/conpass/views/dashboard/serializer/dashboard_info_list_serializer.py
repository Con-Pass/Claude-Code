from rest_framework import serializers


class DashboardInfoListRequestBodySerializer(serializers.Serializer):
    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class DashboardInfoListResponseSerializer(serializers.Serializer):
    """
    ダッシュボード-お知らせ表示項目
    """
    id = serializers.IntegerField()  # ID
    title = serializers.CharField()  # 件名
    message = serializers.CharField(source='body')  # 本文
    url = serializers.CharField()  # URL
    releaseDate = serializers.DateTimeField(source='start_at', format='%Y-%m-%d')  # 開始日(yyyy-mm-dd)


class DashboardInfoListResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """
    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListField(child=DashboardInfoListResponseSerializer(), allow_empty=True)
