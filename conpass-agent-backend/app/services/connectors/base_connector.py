"""
ConnectorAdapter基底クラス
Anthropic knowledge-work-plugins CONNECTORS.md準拠
tool-agnostic設計: カテゴリベースで外部システムを抽象化
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConnectorResult:
    """コネクタ実行結果"""
    source_name: str
    available: bool
    data: list[dict] = field(default_factory=list)
    error: Optional[str] = None


class BaseConnector(ABC):
    """全コネクタの基底クラス"""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """コネクタのソース名を返す"""
        ...

    @abstractmethod
    async def search(self, query: str, account_id: str, **kwargs) -> ConnectorResult:
        """クエリに基づいてデータを検索する"""
        ...

    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[dict]:
        """IDを指定してデータを取得する"""
        ...
