import datetime
from rest_framework import serializers
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class InfoEditGetRequestBodySerializer(serializers.Serializer):
    """
    表示用(GET)
    """
    id = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        return attr


class InfoEditRequestBodySerializer(serializers.Serializer):
    """
    更新用(POST)
    """
    id = serializers.IntegerField(allow_null=True, required=False)
    title = serializers.CharField(max_length=255, error_messages={'blank': '件名を入力してください'})
    body = serializers.CharField(error_messages={'blank': '本文を入力してください'})
    url = serializers.CharField(max_length=255, allow_blank=True, required=False,
                                error_messages={'max_length': 'URLは255文字以内で入力してください'})
    order = serializers.IntegerField(min_value=1, error_messages={'invalid': '優先順位に1以上の整数を入力してください',
                                                                  'min_value': '優先順位に1以上の整数を入力してください'})
    status = serializers.IntegerField()
    startDate = serializers.DateField(error_messages={'invalid': '配信開始日を入力してください'})
    startTime = serializers.TimeField(error_messages={'invalid': '配信開始時間を入力してください'})
    endDate = serializers.DateField(error_messages={'invalid': '配信終了日を入力してください'})
    endTime = serializers.TimeField(error_messages={'invalid': '配信終了時間を入力してください'})

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attr):
        # 配信終了日時が配信開始日時を逆転していないか
        start_at = datetime.datetime.combine(attr.get('startDate'), attr.get('startTime'))
        end_at = datetime.datetime.combine(attr.get('endDate'), attr.get('endTime'))

        if start_at > end_at:
            raise serializers.ValidationError({'endDate': '終了日時には開始日時以降の日時を入力してください'})

        return attr


class InfoEditResponseSerializer(serializers.Serializer):
    """
    お知らせ修正表示項目
    """
    id = serializers.IntegerField()
    title = serializers.CharField()
    body = serializers.CharField()
    url = serializers.CharField()
    order = serializers.IntegerField()
    status = serializers.IntegerField()
    startDate = serializers.DateField(source='start_date', format='%Y-%m-%d')
    startTime = serializers.TimeField(source='start_time', format='%H:%M')
    endDate = serializers.DateField(source='end_date', format='%Y-%m-%d')
    endTime = serializers.TimeField(source='end_time', format='%H:%M')
    createdAt = serializers.DateTimeField(source='created_at', format='%Y-%m-%d %H:%M:%S')
    createdBy = UserResponseSerializerEasy(source='created_by')
    updatedAt = serializers.DateTimeField(source='updated_at', format='%Y-%m-%d %H:%M:%S')
    updatedBy = UserResponseSerializerEasy(source='updated_by')


class InfoEditResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """
    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = InfoEditResponseSerializer()
