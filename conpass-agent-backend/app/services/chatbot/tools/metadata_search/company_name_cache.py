"""
Company name cache service for fetching and caching unique company names from Qdrant.
This service is used for fuzzy matching to handle variations in company name inputs.

SECURITY: Caches are isolated per unique set of directory_ids to ensure users only
see company names from directories they have permission to access.
"""

from typing import Set, List, Optional, Dict, Tuple
from datetime import datetime, timedelta
import asyncio

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.chatbot.tools.metadata_search.qdrant_client import (
    scroll_qdrant_with_filter,
)

logger = get_logger(__name__)

# Cache configuration
CACHE_TTL_HOURS = 24  # Cache company names for 24 hours


# Cache entry structure
class CacheEntry:
    """Cache entry with data and timestamp for TTL tracking."""

    def __init__(self, company_names: Set[str], timestamp: datetime):
        self.company_names = company_names
        self.timestamp = timestamp


# Multi-tenant cache: directory_ids tuple -> CacheEntry
# Key is a sorted tuple of directory_ids to ensure consistent cache keys
_company_names_cache: Dict[Tuple[int, ...], CacheEntry] = {}
_cache_lock = asyncio.Lock()


def _get_cache_key(directory_ids: List[int]) -> Tuple[int, ...]:
    """
    Generate a cache key from directory_ids.

    Sorts and converts to tuple to ensure consistent keys regardless of input order.
    e.g., [2, 1, 3] and [1, 2, 3] both produce (1, 2, 3)

    Args:
        directory_ids: List of directory IDs

    Returns:
        Sorted tuple of directory IDs for use as cache key
    """
    return tuple(sorted(set(directory_ids)))  # Sort and deduplicate


def _is_cache_valid(cache_entry: CacheEntry) -> bool:
    """
    Check if a cache entry is still valid based on TTL.

    Args:
        cache_entry: The cache entry to validate

    Returns:
        True if cache entry is still valid, False if expired
    """
    age = datetime.now() - cache_entry.timestamp
    return age < timedelta(hours=CACHE_TTL_HOURS)


async def _fetch_company_names_from_qdrant(
    directory_ids: List[int],
) -> Set[str]:
    """
    Fetch all unique company names from Qdrant for the given directory IDs.

    Args:
        directory_ids: List of directory IDs to fetch company names from

    Returns:
        Set of unique company names (non-empty strings only)
    """
    logger.info(
        f"Fetching company names from Qdrant for directory_ids: {directory_ids}"
    )

    collection_name = settings.QDRANT_COLLECTION
    if not collection_name:
        logger.error("QDRANT_COLLECTION not configured")
        return set()

    # Build filter for directory_ids
    qdrant_filter = {
        "must": [
            {
                "key": "directory_id",
                # Always use "any" with a list for consistent typing
                "match": {
                    "any": directory_ids
                    if len(directory_ids) > 1
                    else [directory_ids[0]]
                },
            }
        ]
    }

    try:
        # Scroll all points with the filter
        results = await scroll_qdrant_with_filter(
            collection_name=collection_name,
            qdrant_filter=qdrant_filter,
        )

        # Extract unique company names from all company fields
        company_names: Set[str] = set()
        company_fields = [
            "会社名_甲_company_a",
            "会社名_乙_company_b",
            "会社名_丙_company_c",
            "会社名_丁_company_d",
        ]

        for result in results:
            payload = result.get("payload", {})
            for field in company_fields:
                company_name = payload.get(field)
                # Only add non-empty, non-null company names
                if (
                    company_name
                    and isinstance(company_name, str)
                    and company_name.strip()
                ):
                    company_names.add(company_name.strip())

        logger.info(f"Fetched {len(company_names)} unique company names from Qdrant")
        return company_names

    except Exception as e:
        logger.exception(f"Error fetching company names from Qdrant: {e}")
        return set()


async def get_company_names(
    directory_ids: List[int],
    force_refresh: bool = False,
) -> Set[str]:
    """
    Get unique company names for the given directory IDs.
    Uses cache if available and valid, otherwise fetches from Qdrant.

    SECURITY: Each unique set of directory_ids has its own isolated cache entry.
    Users can only see company names from directories they have permission to access.

    Args:
        directory_ids: List of directory IDs to fetch company names from
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        Set of unique company names for the specified directories
    """
    global _company_names_cache

    if not directory_ids:
        logger.warning("Empty directory_ids provided, returning empty set")
        return set()

    # Generate cache key from directory_ids
    cache_key = _get_cache_key(directory_ids)

    async with _cache_lock:
        # Check if we have a valid cache entry for this specific set of directories
        cache_entry = _company_names_cache.get(cache_key)

        if force_refresh or cache_entry is None or not _is_cache_valid(cache_entry):
            if force_refresh:
                logger.info(
                    f"Force refresh requested for directory_ids={directory_ids}, fetching from Qdrant"
                )
            elif cache_entry is None:
                logger.info(
                    f"No cache entry found for directory_ids={directory_ids}, fetching from Qdrant"
                )
            else:
                logger.info(
                    f"Cache expired for directory_ids={directory_ids}, fetching from Qdrant"
                )

            # Fetch fresh data
            company_names = await _fetch_company_names_from_qdrant(directory_ids)

            # Store in cache with timestamp
            _company_names_cache[cache_key] = CacheEntry(
                company_names=company_names, timestamp=datetime.now()
            )

            return company_names
        else:
            # Use cached data
            cache_age = datetime.now() - cache_entry.timestamp
            logger.info(
                f"Using cached company names for directory_ids={directory_ids} "
                f"(cache age: {cache_age}, size: {len(cache_entry.company_names)})"
            )
            return cache_entry.company_names

    return set()


async def invalidate_cache(directory_ids: Optional[List[int]] = None):
    """
    Invalidate the company name cache, forcing a refresh on next access.

    Args:
        directory_ids: If provided, only invalidate cache for these specific directories.
                      If None, invalidate all cache entries.
    """
    global _company_names_cache

    async with _cache_lock:
        if directory_ids is None:
            # Invalidate all cache entries
            logger.info(
                f"Invalidating all cache entries (total: {len(_company_names_cache)})"
            )
            _company_names_cache.clear()
        else:
            # Invalidate specific cache entry
            cache_key = _get_cache_key(directory_ids)
            if cache_key in _company_names_cache:
                logger.info(f"Invalidating cache for directory_ids={directory_ids}")
                del _company_names_cache[cache_key]
            else:
                logger.info(
                    f"No cache entry found for directory_ids={directory_ids}, nothing to invalidate"
                )


def get_cache_info(directory_ids: Optional[List[int]] = None) -> dict:
    """
    Get information about the current cache state.

    Args:
        directory_ids: If provided, get info for specific directories.
                      If None, get summary of all cache entries.

    Returns:
        Dictionary with cache information
    """
    if directory_ids is None:
        # Return summary of all cache entries
        total_entries = len(_company_names_cache)
        total_companies = sum(
            len(entry.company_names) for entry in _company_names_cache.values()
        )

        # Get info about each cache entry
        entries_info = []
        for cache_key, entry in _company_names_cache.items():
            age = datetime.now() - entry.timestamp
            entries_info.append(
                {
                    "directory_ids": list(cache_key),
                    "company_count": len(entry.company_names),
                    "cache_timestamp": entry.timestamp.isoformat(),
                    "cache_age_seconds": age.total_seconds(),
                    "is_valid": _is_cache_valid(entry),
                }
            )

        return {
            "total_cache_entries": total_entries,
            "total_companies_cached": total_companies,
            "ttl_hours": CACHE_TTL_HOURS,
            "entries": entries_info,
        }
    else:
        # Return info for specific directory_ids
        cache_key = _get_cache_key(directory_ids)
        cache_entry = _company_names_cache.get(cache_key)

        if cache_entry is None:
            return {
                "directory_ids": directory_ids,
                "cache_exists": False,
                "is_valid": False,
                "cache_size": 0,
                "ttl_hours": CACHE_TTL_HOURS,
            }

        age = datetime.now() - cache_entry.timestamp
        return {
            "directory_ids": directory_ids,
            "cache_exists": True,
            "is_valid": _is_cache_valid(cache_entry),
            "cache_size": len(cache_entry.company_names),
            "cache_timestamp": cache_entry.timestamp.isoformat(),
            "cache_age_seconds": age.total_seconds(),
            "ttl_hours": CACHE_TTL_HOURS,
        }
