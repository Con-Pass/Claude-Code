"""
機能フラグ管理モジュール。

Firestoreベースの機能フラグで、セッションIDハッシュによる
実験グループ割当を行う。A/Bテスト基盤としても使用する。
"""

import hashlib
import os
from typing import Any, Dict, Optional

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# デフォルトの機能フラグ（環境変数で上書き可能）
# MULTI_AGENT_ENABLED が true の場合は USE_MULTI_AGENT も true として扱う
_multi_agent_env = (
    os.getenv("MULTI_AGENT_ENABLED", "false").lower() == "true"
    or os.getenv("USE_MULTI_AGENT", "false").lower() == "true"
)
DEFAULT_FLAGS: Dict[str, Any] = {
    "use_multi_agent": _multi_agent_env,
    "multi_agent_rollout_pct": int(os.getenv("MULTI_AGENT_ROLLOUT_PCT", "0")),
    "use_reranker": os.getenv("RERANKER_ENABLED", "false").lower() == "true",
    "query_expansion_enabled": os.getenv("QUERY_EXPANSION_ENABLED", "false").lower() == "true",
    "search_cache_enabled": os.getenv("SEARCH_CACHE_ENABLED", "false").lower() == "true",
    "rrf_k": int(os.getenv("RRF_K", "60")),
    "dense_threshold": float(os.getenv("DENSE_SCORE_THRESHOLD", "0.25")),
    "max_chunks_per_contract": int(os.getenv("MAX_CHUNKS_PER_CONTRACT", "3")),
}

# Firestoreからの動的フラグ（キャッシュ）
_dynamic_flags: Optional[Dict[str, Any]] = None


def _session_in_rollout(session_id: str, rollout_pct: int) -> bool:
    """セッションIDのハッシュに基づいてロールアウト対象かを判定。"""
    if rollout_pct >= 100:
        return True
    if rollout_pct <= 0:
        return False
    hash_int = int(hashlib.md5(session_id.encode()).hexdigest(), 16) % 100
    return hash_int < rollout_pct


def get_flag(flag_name: str, session_id: Optional[str] = None) -> Any:
    """
    機能フラグの値を取得する。

    Args:
        flag_name: フラグ名
        session_id: セッションID（ロールアウト判定に使用）

    Returns:
        フラグの値
    """
    flags = {**DEFAULT_FLAGS}
    if _dynamic_flags:
        flags.update(_dynamic_flags)

    value = flags.get(flag_name)

    # マルチエージェントのロールアウト判定
    if flag_name == "use_multi_agent" and session_id:
        rollout_pct = flags.get("multi_agent_rollout_pct", 0)
        if rollout_pct > 0:
            return _session_in_rollout(session_id, rollout_pct)

    return value


def should_use_multi_agent(session_id: Optional[str] = None) -> bool:
    """マルチエージェントを使用すべきかを判定する。"""
    return bool(get_flag("use_multi_agent", session_id))


async def load_flags_from_firestore() -> None:
    """Firestoreから動的フラグを読み込む（起動時に呼び出し）。"""
    global _dynamic_flags
    try:
        from google.cloud import firestore

        from app.core.config import settings

        db = firestore.AsyncClient(
            project=settings.FIRESTORE_PROJECT_ID,
            database=settings.FIRESTORE_DATABASE_ID,
        )
        doc = await db.collection("feature_flags").document("current").get()
        if doc.exists:
            _dynamic_flags = doc.to_dict()
            logger.info(f"Loaded {len(_dynamic_flags)} feature flags from Firestore")
        else:
            logger.info("No feature flags document in Firestore, using defaults")
    except Exception as e:
        logger.warning(f"Failed to load feature flags from Firestore: {e}")
        _dynamic_flags = None
