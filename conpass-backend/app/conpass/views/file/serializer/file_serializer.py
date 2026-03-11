from rest_framework import serializers

from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy


class FileRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    start = serializers.IntegerField(default=0, allow_null=True)
    count = serializers.IntegerField(default=10, allow_null=True)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class FileListSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    account = serializers.DjangoModelField(verbose_name="Account")  # アカウントID
    name = serializers.CharField()  # ファイル名（管理用の名前）
    type = serializers.IntegerField()  # ファイル種別（契約書、テンプレート、過去契約書、その他）
    description = serializers.CharField()  # 説明
    url = serializers.CharField()  # GCSの実体へのパス
    size = serializers.IntegerField()  # ファイルサイズ（byte）
    status = serializers.IntegerField()  # ステータス（有効無効）
    version = serializers.CharField()  # インポート時の契約書バージョン名
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者


class FileResponseSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    files = serializers.ListField(
        child=FileListSerializer(),
        allow_empty=True
    )


class FileResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = FileResponseSerializer()
    # response = serializers.ListField(
    #    child=FileListSerializer(),
    #    allow_empty=True
    # )


class FileLinkedContractRequestBodySerializer(serializers.Serializer):
    """
    request body serializer
    APIのパラメータをバリデートします
    """
    contractId = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class AccountResponseSerializerEasy(serializers.Serializer):
    """
    IDと名前だけの簡略版
    """
    id = serializers.IntegerField()  # ID
    accuntName = serializers.CharField(source='name')  # 名前


class ParentDirectoryResponseSerializerEasy(serializers.Serializer):
    """
    IDと名前だけの簡略版
    """
    id = serializers.IntegerField()  # ID
    parentDirectoryName = serializers.CharField(source='name')  # 名前


class DirectoryResponseSerializerEasy(serializers.Serializer):
    """
    IDと名前だけの簡略版
    """
    id = serializers.IntegerField()  # ID
    directoryName = serializers.CharField(source='name')  # 名前
    parentInfo = ParentDirectoryResponseSerializerEasy(source='parent')  # 親階層のディレクトリ


class FileUploadStatusListSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    accountInfo = AccountResponseSerializerEasy(source='account')  # アカウントID
    uploadId = serializers.CharField(source='upload_id')  # アップロードID（UUID形式）
    name = serializers.CharField()  # ファイル名（管理用の名前）
    description = serializers.CharField()  # 説明
    type = serializers.IntegerField()  # ファイル種別（契約書、テンプレート、過去契約書、その他）
    size = serializers.IntegerField()  # ファイルサイズ（単位: byte）
    uploadDatetime = serializers.DateTimeField(source='upload_datetime', format="%Y-%m-%d %H:%M:%S")  # アップロード日時
    uploadUser = UserResponseSerializerEasy(source='user')  # アップロードユーザー
    uploadStatus = serializers.IntegerField(source='upload_status')  # アップロード状態
    errorMessage = serializers.CharField(source='error_message')  # エラーメッセージ（アップロード中にエラーが発生した場合、原因を格納）
    directoryInfo = DirectoryResponseSerializerEasy(source='directory')  # ディレクトリID
    zipId = serializers.CharField(source='zip_id')  # zipアップロード履歴のID（PDFに展開した際に元のzipのIDを格納する）
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者


class LinkedFileDeleteRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    fileId = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs
