from rest_framework import serializers
from conpass.models import PermissionCategoryKey


class GroupRequestBodySerializer(serializers.Serializer):
    groupName = serializers.CharField(allow_blank=True, required=False)
    """
    request body serializer
    APIのパラメータをバリデートします
    """

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class GroupDeleteRequestBodySerializer(serializers.Serializer):
    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class GroupResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # グループ名
    description = serializers.CharField()  # コメント
    status = serializers.IntegerField()  # ステータス
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時


class GroupResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListField(
        child=GroupResponseSerializer(),
        allow_empty=True
    )


# class GroupUserResponseSerializer(serializers.Serializer):
#     id = serializers.IntegerField()  # ID
#     name = serializers.CharField(source='username')  # 名前


# class GroupUserResponseBodySerializer(serializers.Serializer):
#     """
#     response body serializer
#     """

#     def __init__(self, data):
#         """
#         DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
#         instanceがシリアライズの対象になる
#         """
#         self.instance = {"response": data}

#     response = serializers.ListField(
#         child=GroupUserResponseSerializer(),
#         allow_empty=True
#     )

class GroupUserResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField(source='username')  # 名前
    permission_category_id = serializers.SerializerMethodField()
    permission_category_name = serializers.SerializerMethodField()

    def get_permission_category_id(self, obj):
        return obj.permission_category_id

    def get_permission_category_name(self, obj):
        permission_category_id = obj.permission_category_id
        try:
            if permission_category_id is not None:
                permission_category_key = PermissionCategoryKey.objects.get(id=permission_category_id)
                return permission_category_key.name
            else:
                return "カスタム"
        except PermissionCategoryKey.DoesNotExist:
            return "カスタム"


class GroupUserResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListField(
        child=GroupUserResponseSerializer(),
        allow_empty=True
    )
