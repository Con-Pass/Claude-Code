"""
ConnectorRegistry: 全コネクタの管理・一括実行
"""
import asyncio
from typing import Optional

from app.core.logging_config import get_logger
from app.services.connectors.base_connector import BaseConnector, ConnectorResult

logger = get_logger(__name__)


class ConnectorRegistry:
    """全コネクタの管理・一括実行"""

    def __init__(self):
        self._connectors: dict[str, BaseConnector] = {}

    def register(self, category: str, connector: BaseConnector) -> None:
        """コネクタをカテゴリ名で登録する"""
        self._connectors[category] = connector
        logger.info(f"Connector registered: {category} -> {connector.source_name}")

    def get(self, category: str) -> Optional[BaseConnector]:
        """カテゴリ名でコネクタを取得する"""
        return self._connectors.get(category)

    @property
    def categories(self) -> list[str]:
        """登録済みカテゴリ一覧を返す"""
        return list(self._connectors.keys())

    async def search_all(
        self, query: str, account_id: str, **kwargs
    ) -> list[ConnectorResult]:
        """全コネクタを並列実行して結果を返す"""

        async def _run_connector(
            category: str, connector: BaseConnector
        ) -> ConnectorResult:
            try:
                return await connector.search(query, account_id, **kwargs)
            except Exception as e:
                logger.exception(f"Connector {category} failed: {e}")
                return ConnectorResult(
                    source_name=connector.source_name,
                    available=False,
                    data=[],
                    error=str(e),
                )

        tasks = [
            _run_connector(cat, conn) for cat, conn in self._connectors.items()
        ]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def search_by_categories(
        self,
        categories: list[str],
        query: str,
        account_id: str,
        **kwargs,
    ) -> list[ConnectorResult]:
        """指定カテゴリのコネクタのみ並列実行して結果を返す"""

        async def _run_connector(connector: BaseConnector) -> ConnectorResult:
            try:
                return await connector.search(query, account_id, **kwargs)
            except Exception as e:
                logger.exception(f"Connector {connector.source_name} failed: {e}")
                return ConnectorResult(
                    source_name=connector.source_name,
                    available=False,
                    data=[],
                    error=str(e),
                )

        connectors = []
        for cat in categories:
            conn = self._connectors.get(cat)
            if conn:
                connectors.append(conn)
            else:
                logger.warning(f"Connector category not found: {cat}")

        tasks = [_run_connector(conn) for conn in connectors]
        results = await asyncio.gather(*tasks)
        return list(results)


def create_default_registry() -> ConnectorRegistry:
    """デフォルトのコネクタレジストリを構築する"""
    from app.services.connectors.clm_connector import CLMConnector
    from app.services.connectors.crm_connector import CRMConnector
    from app.services.connectors.storage_connector import StorageConnector
    from app.services.connectors.mail_connector import MailConnector
    from app.services.connectors.esign_connector import ESignConnector

    registry = ConnectorRegistry()
    registry.register("clm", CLMConnector())
    registry.register("crm", CRMConnector())
    registry.register("storage", StorageConnector())
    registry.register("mail", MailConnector())
    registry.register("esign", ESignConnector())
    return registry
