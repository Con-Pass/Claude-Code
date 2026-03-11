import datetime
import os
import uuid
from logging import getLogger

from enum import Enum

from django.conf import settings
from django.utils.timezone import make_aware

from conpass.models import File, FileUploadStatus, User
from google.cloud import storage
try:
    from conpass.services.gcp.local_storage_mock import get_local_storage as _get_local
    _LOCAL_FALLBACK = True
except ImportError:
    _LOCAL_FALLBACK = False


logger = getLogger(__name__)


class GCSBucketName(Enum):
    API = settings.GCS_BUCKET_NAME_API
    FILE = settings.GCS_BUCKET_NAME_FILE
    WEB = settings.GCS_BUCKET_NAME_WEB
    NATURAL_LANGUAGE = settings.GCS_BUCKET_NAME_NATURAL_LANGUAGE


class GoogleCloudStorage():

    def __init__(self):
        self.user_id = 0

    def get_cloudstorage(self, bucket_name: GCSBucketName = GCSBucketName.FILE):
        project_id = "purple-conpass"
        bucket_name_val = bucket_name.value
        try:
            client = storage.Client(project_id)
            bucket = client.bucket(bucket_name_val)
            # 接続確認: 認証情報がなければここで例外
            import google.auth
            google.auth.default()
            return client, bucket
        except Exception as e:
            if _LOCAL_FALLBACK:
                logger.warning(f'GCS unavailable ({e}), falling back to local storage')
                return _get_local()
            raise

    def set_user_id(self, user_id: int):
        self.user_id = user_id

    def get_blob(self, filepath, bucket):
        return storage.Blob(filepath, bucket)

    def prepare_file_record(self, file_id: int, filename: str, filetype: int):
        """
        conpass_fileで管理するレコードを作成
        GCS上はconpass_file.id で一括管理する予定
        fileidが指定されていて、そのFileが存在しているときは上書きになります
        ファイルの情報はアップロード成功時に更新する
        """
        user = User.objects.select_related('account').filter(id=self.user_id).get()
        account_id = user.account_id
        id = file_id
        if id > 0:
            file = self.get_file_from_id(id)
        else:
            now = make_aware(datetime.datetime.now())
            file = File(account_id=account_id, name=filename, type=filetype, description="", url="", size=0,
                        status=File.Status.DISABLE.value,
                        created_at=now, created_by_id=self.user_id,
                        updated_at=now, updated_by_id=self.user_id)
            file.save()
        return file

    def prepare_file_upload_status_record(self, fileuploadstatus_id: int, filename: str, filetype: int):
        """
        conpass_fileuploadstatusで管理するレコードを作成
        GCS上はconpass_fileuploadstatus.id で一括管理する予定
        conpass_fileuploadstatus_idが指定されていて、そのFileが存在しているときは上書きになります
        ファイルの情報はアップロード成功時に更新する
        """
        user = User.objects.select_related('account').filter(id=self.user_id).get()
        account_id = user.account_id
        id = fileuploadstatus_id
        if id > 0:
            fileuploadstatus = self.get_file_upload_status_id(id)
        else:
            now = make_aware(datetime.datetime.now())
            fileuploadstatus = FileUploadStatus(
                upload_id=str(uuid.uuid4()),
                task_id="",
                name=filename,
                description="",
                type=filetype,
                size=0,
                upload_datetime=now,
                upload_status=FileUploadStatus.UploadStatus.START.value,
                file_path="",
                zip_path="",
                contract_type="",
                renew_notify=0,
                is_provider=0,
                is_meta_check=0,
                is_open=0,
                status=FileUploadStatus.Status.ENABLE.value,
                account_id=account_id,
                user_id=self.user_id,
                created_at=now,
                created_by_id=self.user_id,
                updated_at=now,
                updated_by_id=self.user_id)
            fileuploadstatus.save()
        return fileuploadstatus

    def get_file_from_id(self, id: int) -> File:
        """
        id から File情報を取得
        """
        file_obj = File
        user = User.objects.select_related('account').filter(id=self.user_id).get()
        account_id = user.account_id
        wheres = {
            'pk': id,
            'status': File.Status.ENABLE.value,
            'account_id': account_id
        }
        file = file_obj.objects.filter(**wheres).get()
        return file

    def get_file_upload_status_id(self, id: int) -> FileUploadStatus:
        """
        id から FileUploadStatus情報を取得
        """
        file_upload_status_obj = FileUploadStatus
        user = User.objects.select_related('account').filter(id=self.user_id).get()
        account_id = user.account_id
        wheres = {
            'pk': id,
            'status': File.Status.ENABLE.value,
            'account_id': account_id
        }
        file_upload_status = file_upload_status_obj.filter(**wheres).get()
        return file_upload_status

    def get_gcs_fileinfo(self, file: File) -> (str, str):
        """
        File.nameからgscにアップするURLを作る
        """
        file_url = settings.GCS_FILE_PREFIX + str(file.id)
        ext = file.name.rfind('.')
        if ext > 0:
            file_url += file.name[ext:]
        return file.name, file_url

    def get_gcs_fileinfo2(self, file: FileUploadStatus, is_zip: bool) -> (str, str):
        """
        FileUploadStatus.nameからgscにアップするURLを作る
        """
        prefix = settings.GCS_ZIP_FILE_PREFIX if is_zip else settings.GCS_FILE_PREFIX + 'tmp/'
        file_url = prefix + str(file.id)
        ext = file.name.rfind('.')
        if ext > 0:
            file_url += file.name[ext:]
        return file.name, file_url

    def get_gcs_fileurl_from_id(self, id: int) -> (str, str):
        file = self.get_file_from_id(id)
        return file.name, file.url

    def set_file_info(self, file: File, filename: str, url: str, datatype: int, description: str, size: int, version: str = None):
        """
        ファイル情報をFileに保存します
        """
        user = User.objects.select_related('account').filter(id=self.user_id).get()
        account_id = user.account_id
        now = make_aware(datetime.datetime.now())

        file.account_id = account_id
        file.name = filename
        file.type = datatype
        file.description = description
        file.url = url
        file.size = size
        file.status = File.Status.ENABLE.value
        file.version = version
        file.updated_at = now
        file.updated_by_id = user.id
        file.save()

    def set_file_upload_status_info(
            self,
            fileuploadstatus: FileUploadStatus,
            filename: str,
            description: str,
            datatype: int,
            file_path: str,
            zip_path: str,
            directory_id: int,
            contract_type: str,
            renew_notify: int,
            is_provider: int,
            is_meta_check: int,
            is_open: int):
        """
        ファイル情報をFileUploadStatusに保存します
        """
        user = User.objects.select_related('account').filter(id=self.user_id).get()
        account_id = user.account_id
        now = make_aware(datetime.datetime.now())

        fileuploadstatus.name = filename
        fileuploadstatus.description = description
        fileuploadstatus.type = datatype
        fileuploadstatus.file_path = file_path
        fileuploadstatus.zip_path = zip_path
        fileuploadstatus.directory_id = directory_id
        fileuploadstatus.contract_type = contract_type
        fileuploadstatus.renew_notify = renew_notify
        fileuploadstatus.is_provider = is_provider
        fileuploadstatus.is_meta_check = is_meta_check
        fileuploadstatus.is_open = is_open
        fileuploadstatus.status = FileUploadStatus.Status.ENABLE.value
        fileuploadstatus.account_id = account_id
        fileuploadstatus.user_id = user.id
        fileuploadstatus.updated_at = now
        fileuploadstatus.updated_by_id = user.id
        fileuploadstatus.save()

    def set_file_upload_status_task_id(self, fileuploadstatus: FileUploadStatus, task_id: str):
        now = make_aware(datetime.datetime.now())
        fileuploadstatus.task_id = task_id
        fileuploadstatus.updated_at = now
        fileuploadstatus.updated_by_id = fileuploadstatus.user.id
        fileuploadstatus.save()

    def set_file_upload_status_size(self, fileuploadstatus: FileUploadStatus, size: int):
        now = make_aware(datetime.datetime.now())
        fileuploadstatus.size = size
        fileuploadstatus.updated_at = now
        fileuploadstatus.updated_by_id = fileuploadstatus.user.id
        fileuploadstatus.save()

    def set_file_upload_status_upload_status(self, fileuploadstatus: FileUploadStatus, upload_status: int):
        now = make_aware(datetime.datetime.now())
        fileuploadstatus.upload_status = upload_status
        fileuploadstatus.updated_at = now
        fileuploadstatus.updated_by_id = fileuploadstatus.user.id
        fileuploadstatus.save()

    def set_file_upload_status_error_message(self, fileuploadstatus: FileUploadStatus, error_message: str):
        now = make_aware(datetime.datetime.now())
        fileuploadstatus.error_message = error_message
        fileuploadstatus.updated_at = now
        fileuploadstatus.updated_by_id = fileuploadstatus.user.id
        fileuploadstatus.save()

    def set_file_upload_status_file(self, fileuploadstatus: FileUploadStatus, file_id: int):
        now = make_aware(datetime.datetime.now())
        fileuploadstatus.file_id = file_id
        fileuploadstatus.updated_at = now
        fileuploadstatus.updated_by_id = fileuploadstatus.user.id
        fileuploadstatus.save()
