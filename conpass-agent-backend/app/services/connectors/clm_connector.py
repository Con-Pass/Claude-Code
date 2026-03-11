"""
CLMConnector: ConPass契約台帳APIへのコネクタ
GET /api/v1/contracts/ を通じて契約データを検索・取得する
"""
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.connectors.base_connector import BaseConnector, ConnectorResult

logger = get_logger(__name__)


class CLMConnector(BaseConnector):
    """ConPass契約台帳APIへのコネクタ"""

    @property
    def source_name(self) -> str:
        return "CLM（ConPass契約台帳）"

    async def search(self, query: str, account_id: str, **kwargs) -> ConnectorResult:
        """
        ConPass Django API で契約データを検索する。
        vendor_name で取引先フィルタ、status で ACTIVE/EXPIRED(3年以内)/IN_NEGOTIATION をフィルタ。
        """
        try:
            base_url = settings.CONPASS_API_BASE_URL
            params: dict = {
                "search": query,
                "account_id": account_id,
            }
            status_filter = kwargs.get("status")
            if status_filter:
                params["status"] = status_filter

            vendor_name = kwargs.get("vendor_name")
            if vendor_name:
                params["vendor_name"] = vendor_name

            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(
                    f"{base_url}/contract/paginate",
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
            logger.error(f"CLMConnector HTTP error: {e.response.status_code}")
            return ConnectorResult(
                source_name=self.source_name,
                available=False,
                data=[],
                error=f"HTTP {e.response.status_code}",
            )
        except Exception as e:
            logger.exception(f"CLMConnector search error: {e}")
            return ConnectorResult(
                source_name=self.source_name,
                available=False,
                data=[],
                error=str(e),
            )

    async def get_by_id(self, id: str) -> Optional[dict]:
        """契約IDを指定して契約データを取得する"""
        try:
            base_url = settings.CONPASS_API_BASE_URL
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(
                    f"{base_url}/contract",
                    params={"id": id, "type": 1},
                )
                response.raise_for_status()
                data = response.json()
            return data.get("response", data) if isinstance(data, dict) else data
        except Exception as e:
            logger.exception(f"CLMConnector get_by_id error for {id}: {e}")
            return None
