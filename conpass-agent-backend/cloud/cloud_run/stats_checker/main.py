"""
Cloud Function to check Redis contract count and Qdrant point count across environments.

This script can be deployed as a GCP Cloud Function and called via HTTP GET request.
It will return statistics for all 3 environments (dev, staging, prod).

Environment variables required for each environment:
- DEV_REDIS_URL
- DEV_QDRANT_URL
- DEV_QDRANT_API_KEY

- STAGING_REDIS_URL
- STAGING_QDRANT_URL
- STAGING_QDRANT_API_KEY

- PROD_REDIS_URL
- PROD_QDRANT_URL
- PROD_QDRANT_API_KEY
"""

import os
import logging
from typing import Dict, Any, Optional, List
from redis import Redis
import json
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_redis_contract_count(redis_url: str) -> Optional[int]:
    """
    Get the number of contracts stored in Redis.

    Only counts keys that are purely numeric (contract IDs).

    Args:
        redis_url: Redis connection URL

    Returns:
        Number of contract keys in Redis, or None if error
    """
    try:
        redis_client = Redis.from_url(
            redis_url,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )

        # Use SCAN instead of KEYS to avoid blocking Redis with large key sets
        # SCAN is an iterator-based approach that works efficiently with many keys
        contract_count = 0
        for key in redis_client.scan_iter("*"):
            try:
                # Decode bytes to string
                key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                # Check if key is purely numeric (contract ID)
                if key_str.isdigit():
                    contract_count += 1
            except (UnicodeDecodeError, AttributeError):
                # Skip keys that can't be decoded or aren't strings
                continue

        logger.info(f"Found {contract_count} contracts in Redis (numeric keys only)")

        redis_client.close()
        return contract_count

    except Exception as e:
        logger.error(f"Error connecting to Redis: {e}")
        return None


def get_qdrant_point_count(
    qdrant_url: str, qdrant_api_key: str, collection_name: str
) -> Optional[int]:
    """
    Get the exact number of points in a Qdrant collection.

    Uses direct HTTP API call to the /points/count endpoint for accurate counts.
    This bypasses Pydantic validation issues with the client library.

    Args:
        qdrant_url: Qdrant server URL (e.g., https://your-deployment.qdrant.cloud)
        qdrant_api_key: Qdrant API key
        collection_name: Name of the collection

    Returns:
        Exact number of points in collection, or None if error
    """
    try:
        # Use POST /points/count endpoint for exact count
        # This is more accurate than points_count from collection info
        api_url = f"{qdrant_url.rstrip('/')}/collections/{collection_name}/points/count"

        headers = {"api-key": qdrant_api_key, "Content-Type": "application/json"}

        # Empty body {} to count all points
        response = requests.post(api_url, headers=headers, json={}, timeout=10)
        response.raise_for_status()

        count_data = response.json()

        # Extract count from the response
        # The structure is: {"result": {"count": ...}}
        if "result" in count_data and "count" in count_data["result"]:
            point_count = count_data["result"]["count"]
            logger.info(
                f"Found {point_count} points in Qdrant collection '{collection_name}'"
            )
            return point_count
        else:
            logger.error(f"Unexpected response structure from Qdrant API: {count_data}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP error connecting to Qdrant: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting Qdrant point count: {e}", exc_info=True)
        return None


def get_environment_stats(env_prefix: str) -> Dict[str, Any]:
    """
    Get stats for a specific environment.

    Args:
        env_prefix: Environment prefix (DEV, STAGING, PROD)

    Returns:
        Dictionary with redis_count, qdrant_count, and any errors
    """
    errors: List[str] = []
    stats: Dict[str, Any] = {
        "environment": env_prefix.lower(),
        "redis_contract_count": None,
        "qdrant_point_count": None,
        "errors": errors,
    }

    # Get environment variables
    redis_url = os.getenv(f"{env_prefix}_REDIS_URL")
    qdrant_url = os.getenv(f"{env_prefix}_QDRANT_URL")
    qdrant_api_key = os.getenv(f"{env_prefix}_QDRANT_API_KEY")

    # Collection name is always "contracts"
    qdrant_collection = "contracts"

    # Check for missing environment variables
    missing_vars = []
    if not redis_url:
        missing_vars.append(f"{env_prefix}_REDIS_URL")
    if not qdrant_url:
        missing_vars.append(f"{env_prefix}_QDRANT_URL")
    if not qdrant_api_key:
        missing_vars.append(f"{env_prefix}_QDRANT_API_KEY")

    if missing_vars:
        error_msg = f"Missing environment variables: {', '.join(missing_vars)}"
        logger.warning(error_msg)
        stats["errors"].append(error_msg)
        return stats

    # Get Redis count
    logger.info(f"Checking Redis for {env_prefix}...")
    redis_count = get_redis_contract_count(redis_url)
    if redis_count is not None:
        stats["redis_contract_count"] = redis_count
    else:
        stats["errors"].append("Failed to get Redis count")

    # Get Qdrant count
    logger.info(f"Checking Qdrant for {env_prefix}...")
    qdrant_count = get_qdrant_point_count(qdrant_url, qdrant_api_key, qdrant_collection)
    if qdrant_count is not None:
        stats["qdrant_point_count"] = qdrant_count
        stats["collection_name"] = qdrant_collection
    else:
        stats["errors"].append("Failed to get Qdrant count")

    return stats


def get_all_stats() -> Dict[str, Any]:
    """
    Get statistics for all environments.

    Returns:
        Dictionary with stats for dev, staging, and prod
    """
    environments = ["DEV", "STAGING", "PROD"]

    results: Dict[str, Any] = {"environments": {}}

    for env in environments:
        logger.info(f"\n{'=' * 50}")
        logger.info(f"Checking {env} environment...")
        logger.info(f"{'=' * 50}")

        stats = get_environment_stats(env)
        results["environments"][env.lower()] = stats

    return results


# Cloud Function entry point (HTTP)
def stats_http(request):
    """
    HTTP Cloud Function entry point.

    Args:
        request: Flask request object

    Returns:
        JSON response with stats for all environments
    """
    try:
        stats = get_all_stats()

        # Return formatted JSON response
        return (json.dumps(stats, indent=2), 200, {"Content-Type": "application/json"})

    except Exception as e:
        error_msg = f"Error getting stats: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return (
            json.dumps({"error": error_msg}),
            500,
            {"Content-Type": "application/json"},
        )


# For local testing
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("CONPASS EMBEDDING PIPELINE - ENVIRONMENT STATISTICS")
    print("=" * 70 + "\n")

    stats = get_all_stats()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70 + "\n")

    # Print formatted results
    for env_name, env_stats in stats["environments"].items():
        print(f"\n{env_name.upper()} Environment:")
        print("-" * 50)
        print(f"  Redis Contract Count:   {env_stats['redis_contract_count']}")
        print(f"  Qdrant Point Count:     {env_stats['qdrant_point_count']}")
        if env_stats.get("collection_name"):
            print(f"  Collection Name:        {env_stats['collection_name']}")
        if env_stats["errors"]:
            print(f"  Errors:                 {', '.join(env_stats['errors'])}")

    print("\n" + "=" * 70 + "\n")

    # Also save to JSON file
    output_file = "environment_stats.json"
    with open(output_file, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Results saved to: {output_file}\n")
