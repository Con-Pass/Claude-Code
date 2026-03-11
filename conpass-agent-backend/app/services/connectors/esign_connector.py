"""
ESignConnector: GMO Sign API へのコネクタ
電子署名・電子契約の検索・取得を行う
"""
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.connectors.base_connector import BaseConnector, ConnectorResult

logger = get_logger(__name__)


class ESignConnector(BaseConnector):
    """GMO Sign API へのコネクタ"""

    @property
    def source_name(self) -> str:
        return "ESign（GMO Sign）"

    async def search(self, query: str, account_id: str, **kwargs) -> ConnectorResult:
        """GMO Sign から電子契約を検索する"""
        try:
            base_url = settings.CONPASS_API_BASE_URL
            params: dict = {
                "search": query,
                "account_id": account_id,
            }

            sign_status = kwargs.get("sign_status")
            if sign_status:
                params["sign_status"] = sign_status

            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(
                    f"{base_url}/esign/documents",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            results = data.get("response", data) if isinstance(data, dict) else data
            if not isinstance(results, list):
                results = [results] if results else []

            return ConnectorResult(
                source_name=self.source_name,
                available=True,
                data=results,
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"ESignConnector HTTP error: {e.response.status_code}")
            return ConnectorResult(
                source_name=self.source_name,
                available=False,
                data=[],
                error=f"HTTP {e.response.status_code}",
            )
        except Exception as e:
            logger.exception(f"ESignConnector search error: {e}")
            return ConnectorResult(
                source_name=self.source_name,
                available=False,
                data=[],
                error=str(e),
            )

    async def get_by_id(self, id: str) -> Optional[dict]:
        """電子署名IDを指定して電子契約データを取得する"""
        try:
            base_url = settings.CONPASS_API_BASE_URL
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(
                    f"{base_url}/esign/documents/{id}",
                )
                response.raise_for_status()
                data = response.json()
            return data.get("response", data) if isinstance(data, dict) else data
        except Exception as e:
            logger.exception(f"ESignConnector get_by_id error for {id}: {e}")
            return None
