from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class GoogleCloudStorageUploadSerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    filename = serializers.CharField()
    path = serializers.CharField()
    description = serializers.CharField(required=False, default="")
    datatype = serializers.IntegerField()
    fileid = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class GoogleCloudStorageUploadBlobSerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    filename = serializers.CharField()
    blob = serializers.FileField()
    description = serializers.CharField(required=False, default="")
    datatype = serializers.IntegerField()
    fileid = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class GoogleCloudStorageDownloadSerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    fileid = serializers.IntegerField()
    disposition = serializers.CharField(required=False, default="inline")

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class GoogleCloudStorageResponseBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    account = serializers.DjangoModelField(verbose_name="Account")
    name = serializers.CharField()
    type = serializers.IntegerField()
    description = serializers.CharField()
    url = serializers.CharField()
    size = serializers.IntegerField()
    status = serializers.IntegerField()
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")
    createdBy = UserResponseSerializerEasy(source='created_by')
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")
    updatedBy = UserResponseSerializerEasy(source='updated_by')


class GoogleCloudVisionResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = GoogleCloudStorageResponseBodySerializer()


class GoogleCloudStorageDeleteFilesSerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    ids = serializers.ListField(
        child=serializers.IntegerField(),
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class GoogleCloudStorageDeleteLinkedFileSerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    id = serializers.IntegerField()
    fileId = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs
