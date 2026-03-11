from enum import Enum, unique
from django.db import models
from conpass.models import User, Account, Directory, File
from conpass.models.constants.statusable import Statusable


class FileUploadStatus(models.Model, Statusable):
    """
    アップロード状態を管理
    """

    class Type(Enum):
        CONTRACT = 1  # 通常の契約書
        TEMPLATE = 2  # 契約書のテンプレート
        PAST = 3  # 過去契約書
        BULK = 4  # 一括アップロード
        CONTRACT_QR = 5  # QRコード付きの契約書
        ETC = 10  # その他：契約書系ではない、とりあえずあげておきたいファイル

    class UploadStatus(Enum):
        START = 1  # アップロード開始
        REQUEST = 2  # アップロード先URLを取得
        STORED = 3  # GCSに格納された
        START_ZIP_UPLOAD_TASK = 4  # zipファイルの解析を開始
        COMPLETE_ZIP_UPLOAD_TASK = 5  # zipファイルの解析を終了
        START_SAVE_PDF_FROM_ZIP = 6  # zip解凍されたPDF保存の開始
        COMPLETE_SAVE_PDF_FROM_ZIP = 7  # zip解凍されたPDF保存の終了
        START_CLASSIFY_BY_QR_CODE_PRESENCE = 8  # zip解凍されたPDFの状態チェックを開始
        COMPLETE_CLASSIFY_BY_QR_CODE_PRESENCE = 9  # zip解凍されたPDFの状態チェックを終了
        START_PREDICTION_ON_UPLOAD_TASK = 10  # Predictでメタ情報と本文の取得を開始
        COMPLETE_PREDICTION_ON_UPLOAD_TASK = 11  # Predictでメタ情報と本文の取得を終了
        FINISHED = 12  # アップロード完了

    upload_id = models.CharField(max_length=36)  # アップロードID（UUID形式）
    task_id = models.CharField(max_length=36)  # celeryのtask_id（UUID形式）
    name = models.CharField(max_length=255)  # ファイル名（管理用の名前）
    description = models.CharField(max_length=255)  # 説明
    type = models.IntegerField(Type.CONTRACT.value)  # ファイル種別（契約書、テンプレート、過去契約書、その他）
    size = models.IntegerField(default=0)  # ファイルサイズ（単位: byte）
    upload_datetime = models.DateTimeField()  # アップロード日時
    upload_status = models.IntegerField(UploadStatus.START.value)  # アップロード状態
    error_message = models.CharField(max_length=255)  # エラーメッセージ（アップロード中にエラーが発生した場合、原因を格納）
    file_path = models.FilePathField(max_length=255)  # アップロード後のPDFファイルパス
    zip_path = models.FilePathField(max_length=255)  # zipファイルのパス
    contract_type = models.CharField(max_length=255)  # 契約種別
    is_provider = models.BooleanField(default=False)  # 自社のものかどうか
    is_meta_check = models.BooleanField(default=False)  # メタ情報チェックの有無
    is_open = models.BooleanField(default=False)  # 公開フラグ
    renew_notify = models.BooleanField(default=False)  # 契約更新通知（通知対象にする/通知対象にしない）
    directory = models.ForeignKey(Directory, on_delete=models.DO_NOTHING, related_name='file_upload_status_directory',
                                  blank=True, null=True, default=None)  # ディレクトリID
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='file_upload_status_user', blank=True,
                             null=True, default=None)  # ユーザーID（アップロードユーザー）
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING, related_name='file_upload_status_account',
                                blank=True, null=True, default=None)  # アカウントID
    file = models.ForeignKey(File, on_delete=models.DO_NOTHING, related_name='file_upload_status_file',
                             blank=True, null=True, default=None)  # ファイルID
    zip_id = models.CharField(max_length=36, blank=True, null=True, default=None)  # zipアップロード履歴のID（PDFに展開した際に元のzipのIDを格納する）
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='file_upload_status_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='file_upload_status_updated_by', blank=True,
                                   null=True, default=None)  # 更新者
