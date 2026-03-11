#!/usr/bin/env python3
"""
Script to extract unique contract IDs that were marked as deleted from a CSV file.

The script reads a CSV file and looks for messages in the 'jsonPayload.message' column
that contain 'event type: deleted' and extracts the contract IDs from those messages.

Optionally, it can delete these contract IDs from Redis and Qdrant vector database.

Usage:
    uv run python scripts/delete_contracts.py <path_to_csv_file>

Example:
    uv run python scripts/delete_contracts.py data/deleted_contracts.csv
    uv run python scripts/delete_contracts.py data/deleted_contracts.csv --delete --dry-run
    uv run python scripts/delete_contracts.py data/deleted_contracts.csv --delete --redis-only
    uv run python scripts/delete_contracts.py data/deleted_contracts.csv --delete --qdrant-only
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Set, Tuple

try:
    import pandas as pd
except ImportError:
    print("Error: pandas is required. Install it with: uv add pandas")
    sys.exit(1)

try:
    from redis import Redis
except ImportError:
    Redis = None

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
except ImportError:
    QdrantClient = None
    models = None

try:
    from app.core.config import settings
except ImportError:
    settings = None


def extract_contract_ids_from_message(message: str) -> Set[int]:
    """
    Extract contract IDs from a message string.

    Expected format: 'Agent notification received for contract ids: [104944], event type: deleted'

    Args:
        message: The message string to parse

    Returns:
        Set of contract IDs found in the message
    """
    contract_ids = set[int]()

    if not isinstance(message, str):
        return contract_ids

    # Check if the message contains "event type: deleted"
    if "event type: deleted" not in message.lower():
        return contract_ids

    # Extract contract IDs from bracket notation: [104944] or [104944, 105000]
    # Pattern matches: [ followed by one or more digits (with optional commas and spaces) followed by ]
    pattern = r"\[([\d,\s]+)\]"
    matches = re.findall(pattern, message)

    for match in matches:
        # Split by comma and extract individual IDs
        ids_str = match.split(",")
        for id_str in ids_str:
            id_str = id_str.strip()
            if id_str.isdigit():
                contract_ids.add(int(id_str))

    return contract_ids


def extract_deleted_contract_ids(csv_path: str) -> Set[int]:
    """
    Read CSV file and extract unique contract IDs that were marked as deleted.

    Args:
        csv_path: Path to the CSV file

    Returns:
        Set of unique contract IDs that were deleted
    """
    csv_file = Path(csv_path)

    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Read the CSV file
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        raise ValueError(f"Error reading CSV file: {e}")

    # Check if the required column exists
    column_name = "jsonPayload.message"
    if column_name not in df.columns:
        # Try case-insensitive search
        matching_cols = [
            col for col in df.columns if col.lower() == column_name.lower()
        ]
        if matching_cols:
            column_name = matching_cols[0]
        else:
            raise ValueError(
                f"Column '{column_name}' not found in CSV. Available columns: {list(df.columns)}"
            )

    # Extract contract IDs from all messages
    all_contract_ids = set()

    for message in df[column_name]:
        contract_ids = extract_contract_ids_from_message(message)
        all_contract_ids.update(contract_ids)

    return all_contract_ids


def check_redis_exists(contract_id: int, redis_client: Redis) -> bool:
    """
    Check if a contract exists in Redis.

    Args:
        contract_id: Contract ID to check
        redis_client: Redis client instance

    Returns:
        True if contract exists, False otherwise
    """
    try:
        key = str(contract_id)
        return redis_client.exists(key) > 0
    except Exception:
        return False


def check_qdrant_exists(
    contract_id: int, qdrant_client: QdrantClient, collection_name: str
) -> bool:
    """
    Check if a contract exists in Qdrant.

    Args:
        contract_id: Contract ID to check
        qdrant_client: Qdrant client instance
        collection_name: Name of the Qdrant collection

    Returns:
        True if contract exists, False otherwise
    """
    try:
        # Create filter condition to match contract_id in payload
        filter_condition = models.Filter(
            must=[
                models.FieldCondition(
                    key="contract_id", match=models.MatchValue(value=contract_id)
                )
            ]
        )

        # Search for points matching the filter (limit to 1 for efficiency)
        result = qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=filter_condition,
            limit=1,
        )

        # Check if any points were found
        return len(result[0]) > 0
    except Exception:
        return False


def delete_from_redis(contract_id: int, redis_client: Redis) -> bool:
    """
    Delete a contract from Redis using contract_id as the key.

    Args:
        contract_id: Contract ID to delete
        redis_client: Redis client instance

    Returns:
        True if deletion was successful or key didn't exist, False on error
    """
    try:
        key = str(contract_id)
        result = redis_client.delete(key)
        if result:
            print(f"  ✓ Deleted contract {contract_id} from Redis")
        else:
            print(f"  - Contract {contract_id} not found in Redis")
        return True
    except Exception as e:
        print(f"  ✗ Error deleting contract {contract_id} from Redis: {e}")
        return False


def delete_from_qdrant(
    contract_id: int, qdrant_client: QdrantClient, collection_name: str
) -> bool:
    """
    Delete all Qdrant points associated with a contract_id.

    Args:
        contract_id: Contract ID to delete
        qdrant_client: Qdrant client instance
        collection_name: Name of the Qdrant collection

    Returns:
        True if deletion was successful, False on error
    """
    try:
        # Create filter condition to match contract_id in payload
        filter_condition = models.Filter(
            must=[
                models.FieldCondition(
                    key="contract_id", match=models.MatchValue(value=contract_id)
                )
            ]
        )

        # Delete points matching the filter
        qdrant_client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(filter=filter_condition),
        )

        print(f"  ✓ Deleted contract {contract_id} from Qdrant")
        return True
    except Exception as e:
        print(f"  ✗ Error deleting contract {contract_id} from Qdrant: {e}")
        return False


def delete_contracts_from_storage(
    contract_ids: Set[int],
    delete_redis: bool = True,
    delete_qdrant: bool = True,
    dry_run: bool = False,
) -> Tuple[int, int]:
    """
    Delete contract IDs from Redis and/or Qdrant.

    Args:
        contract_ids: Set of contract IDs to delete
        delete_redis: Whether to delete from Redis
        delete_qdrant: Whether to delete from Qdrant
        dry_run: If True, only show what would be deleted without actually deleting

    Returns:
        Tuple of (successful_deletions, failed_deletions)
    """
    if not contract_ids:
        print("\nNo contract IDs to delete.")
        return (0, 0)

    # Initialize Redis client if needed (for both dry-run and actual deletion)
    redis_client = None
    if delete_redis:
        if Redis is None:
            print(
                "Error: redis package is required for Redis operations. Install it with: uv add redis"
            )
            return (0, len(contract_ids))
        if settings is None:
            print(
                "Error: Could not import app settings. Make sure you're running from the project root."
            )
            return (0, len(contract_ids))

        try:
            redis_client = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=False,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
            if not dry_run:
                print(f"\nConnected to Redis at {settings.REDIS_URL}")
            # In dry-run, connection message is shown later
        except Exception as e:
            print(f"Error connecting to Redis: {e}")
            return (0, len(contract_ids))

    # Initialize Qdrant client if needed (for both dry-run and actual deletion)
    qdrant_client = None
    collection_name = None
    if delete_qdrant:
        if QdrantClient is None or models is None:
            print(
                "Error: qdrant-client package is required for Qdrant operations. Install it with: uv add qdrant-client"
            )
            return (0, len(contract_ids))
        if settings is None:
            print(
                "Error: Could not import app settings. Make sure you're running from the project root."
            )
            return (0, len(contract_ids))

        try:
            qdrant_client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
            )
            collection_name = settings.QDRANT_COLLECTION
            if not dry_run:
                print(
                    f"Connected to Qdrant at {settings.QDRANT_URL} (collection: {collection_name})"
                )
        except Exception as e:
            print(f"Error connecting to Qdrant: {e}")
            return (0, len(contract_ids))

    if dry_run:
        print("\n[DRY RUN] Checking which contracts exist in storage...")
        if redis_client:
            print(f"Connected to Redis at {settings.REDIS_URL}")
        if qdrant_client:
            print(
                f"Connected to Qdrant at {settings.QDRANT_URL} (collection: {collection_name})"
            )
        print()

        found_in_redis = 0
        found_in_qdrant = 0
        not_found_in_redis = 0
        not_found_in_qdrant = 0

        for contract_id in sorted(contract_ids):
            print(f"Contract {contract_id}:")
            status_lines = []

            if delete_redis and redis_client:
                exists = check_redis_exists(contract_id, redis_client)
                if exists:
                    status_lines.append("  ✓ Redis: EXISTS")
                    found_in_redis += 1
                else:
                    status_lines.append("  ✗ Redis: NOT FOUND")
                    not_found_in_redis += 1

            if delete_qdrant and qdrant_client:
                exists = check_qdrant_exists(
                    contract_id, qdrant_client, collection_name
                )
                if exists:
                    status_lines.append("  ✓ Qdrant: EXISTS")
                    found_in_qdrant += 1
                else:
                    status_lines.append("  ✗ Qdrant: NOT FOUND")
                    not_found_in_qdrant += 1

            for line in status_lines:
                print(line)

        print(f"\n{'=' * 60}")
        print("Dry Run Summary:")
        if delete_redis:
            print(f"  Redis: {found_in_redis} found, {not_found_in_redis} not found")
        if delete_qdrant:
            print(f"  Qdrant: {found_in_qdrant} found, {not_found_in_qdrant} not found")
        print(f"{'=' * 60}")
        print("\nNo items were actually deleted (dry-run mode).")
        return (0, 0)

    # Delete contracts (clients are already initialized above)
    print(f"\nDeleting {len(contract_ids)} contract(s)...")
    successful = 0
    failed = 0

    for contract_id in sorted(contract_ids):
        print(f"\nProcessing contract {contract_id}:")
        success = True

        if delete_redis and redis_client:
            if not delete_from_redis(contract_id, redis_client):
                success = False

        if delete_qdrant and qdrant_client:
            if not delete_from_qdrant(contract_id, qdrant_client, collection_name):
                success = False

        if success:
            successful += 1
        else:
            failed += 1

    return (successful, failed)


def main():
    parser = argparse.ArgumentParser(
        description="Extract unique contract IDs marked as deleted from a CSV file"
    )
    parser.add_argument(
        "csv_file",
        type=str,
        help="Path to the CSV file containing the contract deletion messages",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Optional: Output file path to save the contract IDs (one per line)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the extracted contract IDs from Redis and Qdrant",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting (requires --delete)",
    )
    parser.add_argument(
        "--redis-only",
        action="store_true",
        help="Only delete from Redis (requires --delete)",
    )
    parser.add_argument(
        "--qdrant-only",
        action="store_true",
        help="Only delete from Qdrant (requires --delete)",
    )

    args = parser.parse_args()

    # Validate argument combinations
    if args.dry_run and not args.delete:
        print("Error: --dry-run requires --delete", file=sys.stderr)
        return 1

    if args.redis_only and args.qdrant_only:
        print(
            "Error: --redis-only and --qdrant-only cannot be used together",
            file=sys.stderr,
        )
        return 1

    if (args.redis_only or args.qdrant_only) and not args.delete:
        print("Error: --redis-only and --qdrant-only require --delete", file=sys.stderr)
        return 1

    try:
        # Extract contract IDs
        contract_ids = extract_deleted_contract_ids(args.csv_file)

        # Sort for consistent output
        sorted_ids = sorted(contract_ids)

        # Print results
        print(f"\nFound {len(sorted_ids)} unique contract ID(s) marked as deleted:\n")
        for contract_id in sorted_ids:
            print(contract_id)

        # Save to file if output path is provided
        if args.output:
            output_path = Path(args.output)
            with open(output_path, "w") as f:
                for contract_id in sorted_ids:
                    f.write(f"{contract_id}\n")
            print(f"\nContract IDs saved to: {output_path}")

        # Delete from storage if requested
        if args.delete:
            delete_redis = not args.qdrant_only
            delete_qdrant = not args.redis_only

            successful, failed = delete_contracts_from_storage(
                contract_ids=set(sorted_ids),
                delete_redis=delete_redis,
                delete_qdrant=delete_qdrant,
                dry_run=args.dry_run,
            )

            if not args.dry_run:
                print(f"\n{'=' * 60}")
                print("Deletion Summary:")
                print(f"  Successful: {successful}")
                print(f"  Failed: {failed}")
                print(f"{'=' * 60}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
