"""
MailConnector: 通知履歴APIへのコネクタ
契約関連の通知・メール送信履歴を検索・取得する
"""
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.connectors.base_connector import BaseConnector, ConnectorResult

logger = get_logger(__name__)


class MailConnector(BaseConnector):
    """通知履歴APIへのコネクタ"""

    @property
    def source_name(self) -> str:
        return "Mail（通知履歴）"

    async def search(self, query: str, account_id: str, **kwargs) -> ConnectorResult:
        """通知履歴を検索する"""
        try:
            base_url = settings.CONPASS_API_BASE_URL
            params: dict = {
                "search": query,
                "account_id": account_id,
            }

            notification_type = kwargs.get("notification_type")
            if notification_type:
                params["type"] = notification_type

            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(
                    f"{base_url}/notifications",
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
            logger.error(f"MailConnector HTTP error: {e.response.status_code}")
            return ConnectorResult(
                source_name=self.source_name,
                available=False,
                data=[],
                error=f"HTTP {e.response.status_code}",
            )
        except Exception as e:
            logger.exception(f"MailConnector search error: {e}")
            return ConnectorResult(
                source_name=self.source_name,
                available=False,
                data=[],
                error=str(e),
            )

    async def get_by_id(self, id: str) -> Optional[dict]:
        """通知IDを指定して通知データを取得する"""
        try:
            base_url = settings.CONPASS_API_BASE_URL
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(
                    f"{base_url}/notifications/{id}",
                )
                response.raise_for_status()
                data = response.json()
            return data.get("response", data) if isinstance(data, dict) else data
        except Exception as e:
            logger.exception(f"MailConnector get_by_id error for {id}: {e}")
            return None
