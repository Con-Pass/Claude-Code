"""
セマンティック検索結果のインメモリキャッシュ。

同一クエリ + directory_idsの組み合わせに対する結果をTTL付きでキャッシュする。
"""

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# キャッシュ設定（環境変数で上書き可能）
SEARCH_CACHE_ENABLED = os.getenv("SEARCH_CACHE_ENABLED", "false").lower() == "true"
SEARCH_CACHE_TTL_SECONDS = int(os.getenv("SEARCH_CACHE_TTL_SECONDS", "300"))  # 5分
EMBEDDING_CACHE_TTL_SECONDS = int(os.getenv("EMBEDDING_CACHE_TTL_SECONDS", "3600"))  # 1時間
MAX_CACHE_ENTRIES = int(os.getenv("MAX_SEARCH_CACHE_ENTRIES", "500"))

# インメモリキャッシュ
_search_cache: Dict[str, Dict[str, Any]] = {}
_embedding_cache: Dict[str, Dict[str, Any]] = {}


def _make_cache_key(query: str, directory_ids: List[int], extra: str = "") -> str:
    """クエリとdirectory_idsからキャッシュキーを生成する。"""
    key_data = json.dumps({
        "query": query,
        "directory_ids": sorted(directory_ids),
        "extra": extra,
    }, sort_keys=True)
    return hashlib.sha256(key_data.encode()).hexdigest()


def get_cached_search(
    query: str,
    directory_ids: List[int],
) -> Optional[List[Dict[str, Any]]]:
    """キャッシュされた検索結果を取得する。"""
    if not SEARCH_CACHE_ENABLED:
        return None

    key = _make_cache_key(query, directory_ids)
    entry = _search_cache.get(key)
    if entry is None:
        return None

    if time.time() - entry["timestamp"] > SEARCH_CACHE_TTL_SECONDS:
        del _search_cache[key]
        return None

    logger.info(f"Search cache hit: query='{query[:50]}...'")
    return entry["results"]


def set_cached_search(
    query: str,
    directory_ids: List[int],
    results: List[Dict[str, Any]],
) -> None:
    """検索結果をキャッシュに保存する。"""
    if not SEARCH_CACHE_ENABLED:
        return

    # キャッシュサイズ制限
    if len(_search_cache) >= MAX_CACHE_ENTRIES:
        _evict_oldest(_search_cache)

    key = _make_cache_key(query, directory_ids)
    _search_cache[key] = {
        "results": results,
        "timestamp": time.time(),
    }


def get_cached_embedding(
    query: str,
    model: str = "",
) -> Optional[List[float]]:
    """キャッシュされたEmbeddingを取得する。"""
    if not SEARCH_CACHE_ENABLED:
        return None

    key = _make_cache_key(query, [], extra=model)
    entry = _embedding_cache.get(key)
    if entry is None:
        return None

    if time.time() - entry["timestamp"] > EMBEDDING_CACHE_TTL_SECONDS:
        del _embedding_cache[key]
        return None

    return entry["embedding"]


def set_cached_embedding(
    query: str,
    embedding: List[float],
    model: str = "",
) -> None:
    """Embeddingをキャッシュに保存する。"""
    if not SEARCH_CACHE_ENABLED:
        return

    if len(_embedding_cache) >= MAX_CACHE_ENTRIES:
        _evict_oldest(_embedding_cache)

    key = _make_cache_key(query, [], extra=model)
    _embedding_cache[key] = {
        "embedding": embedding,
        "timestamp": time.time(),
    }


def _evict_oldest(cache: Dict[str, Dict[str, Any]]) -> None:
    """最も古いエントリを削除する。"""
    if not cache:
        return
    oldest_key = min(cache, key=lambda k: cache[k]["timestamp"])
    del cache[oldest_key]


def clear_cache() -> None:
    """全キャッシュをクリアする。"""
    _search_cache.clear()
    _embedding_cache.clear()
