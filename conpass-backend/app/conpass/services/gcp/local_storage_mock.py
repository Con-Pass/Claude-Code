"""
ローカル開発用: GCSをローカルファイルシステムに置き換えるモジュール
"""
import os
import shutil
from logging import getLogger

logger = getLogger(__name__)

UPLOAD_DIR = "/app/media/uploads"
LOCAL_FILE_ENDPOINT = "/api/local-file"


class LocalBlob:
    """GCS Blob のローカル実装"""
    def __init__(self, gcs_path: str):
        self.gcs_path = gcs_path
        self.local_path = os.path.join(UPLOAD_DIR, gcs_path.replace("/", "_"))

    def upload_from_file(self, file_obj):
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_obj.seek(0)
        with open(self.local_path, 'wb') as f:
            shutil.copyfileobj(file_obj, f)
        logger.info(f"[LocalStorage] Saved: {self.local_path}")

    def generate_signed_url(self, expiration=None, method='GET',
                            response_disposition=None,
                            response_type=None, **kwargs):
        """GCS署名付きURLの代わりにローカルファイルサーバーのURLを返す"""
        import urllib.parse
        path_encoded = urllib.parse.quote(self.gcs_path, safe='')
        url = f"{LOCAL_FILE_ENDPOINT}?path={path_encoded}"
        logger.info(f"[LocalStorage] Signed URL (local): {url}")
        return url

    def exists(self):
        return os.path.exists(self.local_path)

    def download_to_filename(self, dest):
        shutil.copy2(self.local_path, dest)

    def download_as_bytes(self):
        with open(self.local_path, 'rb') as f:
            return f.read()

    @property
    def public_url(self):
        import urllib.parse
        path_encoded = urllib.parse.quote(self.gcs_path, safe='')
        return f"{LOCAL_FILE_ENDPOINT}?path={path_encoded}"


class LocalBucket:
    """GCS Bucket のローカル実装"""
    def __init__(self):
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    def blob(self, gcs_path: str) -> LocalBlob:
        return LocalBlob(gcs_path)


class LocalStorageClient:
    """GCS Client のローカル実装"""
    def bucket(self, name: str) -> LocalBucket:
        return LocalBucket()


def get_local_storage():
    """(client, bucket) のローカル版を返す"""
    return LocalStorageClient(), LocalBucket()
