from app.core.config import settings


def is_production() -> bool:
    return settings.ENVIRONMENT == "production"


def is_staging() -> bool:
    return settings.ENVIRONMENT == "staging"


def is_development() -> bool:
    return settings.ENVIRONMENT == "development" or settings.ENVIRONMENT == "test"


def is_multi_agent_enabled() -> bool:
    """マルチエージェントが有効かを判定する。

    MULTI_AGENT_ENABLED 環境変数で制御。
    開発環境ではデフォルト False、本番では環境変数で True に設定する。
    """
    return settings.MULTI_AGENT_ENABLED
