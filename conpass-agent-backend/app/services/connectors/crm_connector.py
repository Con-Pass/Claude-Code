"""
CRMConnector: 顧客・取引先マスタへのコネクタ
GET /api/v1/clients/ を通じて取引先データを検索・取得する
"""
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.connectors.base_connector import BaseConnector, ConnectorResult

logger = get_logger(__name__)


class CRMConnector(BaseConnector):
    """顧客・取引先マスタへのコネクタ"""

    @property
    def source_name(self) -> str:
        return "CRM（顧客・取引先マスタ）"

    async def search(self, query: str, account_id: str, **kwargs) -> ConnectorResult:
        """取引先マスタから顧客・取引先を検索する"""
        try:
            base_url = settings.CONPASS_API_BASE_URL
            params: dict = {
                "search": query,
                "account_id": account_id,
            }

            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(
                    f"{base_url}/clients",
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
            logger.error(f"CRMConnector HTTP error: {e.response.status_code}")
            return ConnectorResult(
                source_name=self.source_name,
                available=False,
                data=[],
                error=f"HTTP {e.response.status_code}",
            )
        except Exception as e:
            logger.exception(f"CRMConnector search error: {e}")
            return ConnectorResult(
                source_name=self.source_name,
                available=False,
                data=[],
                error=str(e),
            )

    async def get_by_id(self, id: str) -> Optional[dict]:
        """取引先IDを指定して取引先データを取得する"""
        try:
            base_url = settings.CONPASS_API_BASE_URL
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(
                    f"{base_url}/clients/{id}",
                )
                response.raise_for_status()
                data = response.json()
            return data.get("response", data) if isinstance(data, dict) else data
        except Exception as e:
            logger.exception(f"CRMConnector get_by_id error for {id}: {e}")
            return None
