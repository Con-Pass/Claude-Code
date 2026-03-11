"""
StorageConnector: GCP Cloud Storage へのコネクタ
契約書PDFや添付ファイルの検索・取得を行う
"""
from typing import Optional

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.connectors.base_connector import BaseConnector, ConnectorResult

logger = get_logger(__name__)


class StorageConnector(BaseConnector):
    """GCP Cloud Storage へのコネクタ"""

    @property
    def source_name(self) -> str:
        return "Storage（GCP Cloud Storage）"

    async def search(self, query: str, account_id: str, **kwargs) -> ConnectorResult:
        """
        Cloud Storage 上のファイルを検索する。
        バケット名とプレフィックスでフィルタリング。
        """
        try:
            from google.cloud import storage as gcs

            bucket_name = settings.GCS_BUCKET_NAME
            prefix = kwargs.get("prefix", f"accounts/{account_id}/")

            client = gcs.Client()
            bucket = client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=prefix, max_results=50)

            results = []
            query_lower = query.lower()
            for blob in blobs:
                if query_lower in blob.name.lower():
                    results.append({
                        "name": blob.name,
                        "size": blob.size,
                        "content_type": blob.content_type,
                        "updated": blob.updated.isoformat() if blob.updated else None,
                        "bucket": bucket_name,
                    })

            return ConnectorResult(
                source_name=self.source_name,
                available=True,
                data=results,
            )
        except ImportError:
            logger.warning("google-cloud-storage not installed, StorageConnector unavailable")
            return ConnectorResult(
                source_name=self.source_name,
                available=False,
                data=[],
                error="google-cloud-storage パッケージが未インストール",
            )
        except Exception as e:
            logger.exception(f"StorageConnector search error: {e}")
            return ConnectorResult(
                source_name=self.source_name,
                available=False,
                data=[],
                error=str(e),
            )

    async def get_by_id(self, id: str) -> Optional[dict]:
        """
        blob名を指定してファイルメタデータを取得する。
        id は "bucket_name/blob_path" 形式。
        """
        try:
            from google.cloud import storage as gcs

            bucket_name = settings.GCS_BUCKET_NAME
            blob_path = id

            client = gcs.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_path)

            if not blob.exists():
                return None

            blob.reload()
            return {
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_type,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "bucket": bucket_name,
            }
        except Exception as e:
            logger.exception(f"StorageConnector get_by_id error for {id}: {e}")
            return None
