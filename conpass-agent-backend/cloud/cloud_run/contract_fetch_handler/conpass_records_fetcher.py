import os
import datetime
import math
import pymysql
import json
import logging
from redis import Redis
from google.cloud import pubsub_v1
from google.cloud import scheduler_v1
import functions_framework
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


publisher = pubsub_v1.PublisherClient()
scheduler_client = scheduler_v1.CloudSchedulerClient()
project_id = os.getenv("GCP_PROJECT", "conpass-agent")


class BaseConfig:
    BATCH_SIZE = 10
    FETCH_LIMIT = 1000
    REDIS_LAST_ID_KEY = "conpass:last_contract_id"
    REDIS_LARGE_CONTRACT_KEY_PREFIX = "conpass:large_contract:"
    REDIS_TRUNCATED_CONTRACT_KEY_PREFIX = "conpass:truncated_contract:"

    def __init__(self) -> None:
        self.SCHEDULER_JOB_NAME = os.getenv(
            "SCHEDULER_JOB_NAME", "record-fetcher-schedular"
        )
        # common database config
        self.DB_USER = os.getenv("DB_USER")
        self.DB_PASS = os.getenv("DB_PASS")
        self.DB_NAME = os.getenv("DB_NAME")
        try:
            self.DB_PORT = int(os.getenv("DB_PORT", 3306))
        except ValueError:
            self.DB_PORT = 3306
        # These are set by subclasses, but defined here for type checking
        self.REDIS_URL: Optional[str] = None
        self.PUBSUB_TOPIC: Optional[str] = None
        self.DB_HOST: Optional[str] = None


class TestConfig(BaseConfig):
    def __init__(self) -> None:
        super().__init__()
        self.REDIS_URL = os.getenv("REDIS_URL_TEST", "redis://localhost:6379/0")
        self.PUBSUB_TOPIC = os.getenv("PUBSUB_TOPIC_TEST", "conpass-agent-pubsub")
        # Database Config
        self.DB_HOST = os.getenv("DB_HOST_TEST")


class StagingConfig(BaseConfig):
    def __init__(self) -> None:
        super().__init__()
        self.REDIS_URL = os.getenv("REDIS_URL_STAGE", "redis://localhost:6379/0")
        self.PUBSUB_TOPIC = os.getenv(
            "PUBSUB_TOPIC_STAGE", "conpass-agent-pubsub-staging"
        )
        # Database Config
        self.DB_HOST = os.getenv("DB_HOST_STAGE")


class ProductionConfig(BaseConfig):
    def __init__(self) -> None:
        super().__init__()
        self.REDIS_URL = os.getenv("REDIS_URL_PROD", "redis://localhost:6379/0")
        self.PUBSUB_TOPIC = os.getenv("PUBSUB_TOPIC_PROD", "conpass-agent-pubsub-prod")
        # Database Config
        self.DB_HOST = os.getenv("DB_HOST_PROD")
        self.DB_PASS = os.getenv("DB_PASS_PROD")


CONFIGS = {
    "test": TestConfig,
    "staging": StagingConfig,
    "production": ProductionConfig,
}

APP_ENV = "production"  # "test", "staging", "production"
config = CONFIGS.get(APP_ENV, TestConfig)()

logger.info(f"Running in {APP_ENV} mode using {config.__class__.__name__}")

topic_path = publisher.topic_path(project_id, config.PUBSUB_TOPIC)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that converts datetime/date objects to strings."""

    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)


def get_mysql_connection():
    """
    Create and return a MySQL database connection using environment variables.

    Returns:
        pymysql.Connection: Database connection object, or None if connection fails.
    """
    host = config.DB_HOST
    user = config.DB_USER
    password = config.DB_PASS
    database = config.DB_NAME
    port = config.DB_PORT

    # Validate required environment variables
    if not all([host, user, password, database]):
        logger.error(
            "Missing required database config values (host/user/password/database)"
        )
        return None

    try:
        connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor,
        )
        return connection
    except pymysql.Error as e:
        logger.error(f"Database connection failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during connection: {str(e)}")
        return None


# Redis client
def get_redis_client() -> Optional[Redis]:
    try:
        # Redis URL may be like redis://:password@host:port/db
        return Redis.from_url(config.REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.warning("Failed to create Redis client: %s", e)
        return None


def get_large_contract_ids_from_redis(redis_client: Redis) -> list[int]:
    """Get all contract IDs that are marked as large contracts in Redis using SCAN."""
    try:
        pattern = f"{config.REDIS_LARGE_CONTRACT_KEY_PREFIX}*"
        contract_ids = []
        # Use scan_iter instead of keys to avoid blocking Redis
        for key in redis_client.scan_iter(match=pattern):
            # Extract contract ID from key: "conpass:large_contract:123" -> 123
            contract_id_str = key.replace(config.REDIS_LARGE_CONTRACT_KEY_PREFIX, "")
            try:
                contract_ids.append(int(contract_id_str))
            except ValueError:
                logger.warning(f"Invalid contract ID in Redis key: {key}")
        return contract_ids
    except Exception as e:
        logger.error(f"Error getting large contract IDs from Redis: {e}")
        return []


def enable_scheduler():
    job_path = scheduler_client.job_path(
        project_id, "asia-northeast1", config.SCHEDULER_JOB_NAME
    )
    scheduler_client.resume_job(name=job_path)
    logger.info(f"Enabled scheduler for job: {job_path}")


def disable_scheduler():
    job_path = scheduler_client.job_path(
        project_id, "asia-northeast1", config.SCHEDULER_JOB_NAME
    )
    scheduler_client.pause_job(name=job_path)
    logger.info(f"Disabled scheduler for job: {job_path}")


def calculate_contract_size(contract: dict) -> int:
    """Calculate the size in bytes of a single contract when serialized to JSON."""
    contract_json = json.dumps(contract, ensure_ascii=False, cls=DateTimeEncoder)
    return len(contract_json.encode("utf-8"))


def truncate_contract_body(contract: dict, max_body_bytes: int) -> dict:
    """
    Truncate the contract body to fit within max_body_bytes.
    Returns a copy of the contract with truncated body.
    """
    truncated_contract = contract.copy()
    if "body" in truncated_contract and truncated_contract["body"]:
        body = truncated_contract["body"]
        if isinstance(body, str):
            body_bytes = body.encode("utf-8")
            if len(body_bytes) > max_body_bytes:
                # Truncate to max_body_bytes, ensuring we don't break UTF-8 characters
                truncated_body_bytes = body_bytes[:max_body_bytes]
                # Remove any incomplete UTF-8 character at the end
                while (
                    truncated_body_bytes and (truncated_body_bytes[-1] & 0xC0) == 0x80
                ):
                    truncated_body_bytes = truncated_body_bytes[:-1]
                truncated_contract["body"] = truncated_body_bytes.decode(
                    "utf-8", errors="ignore"
                )
                logger.info(
                    f"Truncated contract {contract.get('id')} body from {len(body_bytes)} to {len(truncated_body_bytes)} bytes"
                )
    return truncated_contract


@functions_framework.http
def fetch_and_publish(request):
    """Fetches contract data from the MySQL DB and publishes to Pub/Sub."""
    is_manual_run = request.args.get("manual", "false").lower() == "true"
    if is_manual_run:
        enable_scheduler()

    conn = get_mysql_connection()
    if not conn:
        return ("Database connection failed", 500)

    # Get Redis client
    redis_client = get_redis_client()
    if not redis_client:
        return ("Redis client failed", 500)
    try:
        with conn.cursor() as cursor:
            # Get last ID from Redis
            last_id = int(redis_client.get(config.REDIS_LAST_ID_KEY) or 0)
            max_id_in_run = last_id
            logger.info(f"Last ID: {last_id}")

            # Check if last_contract_id exceeds the test limit (5000)
            ###### TODO: Remove the below block after testing
            # TEST_LIMIT = 5000
            # if last_id >= TEST_LIMIT:
            #     logger.info(
            #         f"Last contract ID ({last_id}) has reached or exceeded test limit ({TEST_LIMIT}). "
            #         f"Stopping scheduler and exiting."
            #     )
            #     disable_scheduler()
            #     return (
            #         f"Test limit reached: last_contract_id ({last_id}) >= {TEST_LIMIT}. Scheduler disabled.",
            #         200,
            #     )
            ###### Block end
            cursor.execute(
                "SELECT COUNT(*) AS total FROM conpass_contract WHERE type = 1 AND status NOT IN (0, 10, 11, 20) AND is_garbage = False;"
            )
            total_available_contracts = cursor.fetchone()["total"]
            logger.info(
                f"Total available contracts (type = 1, status NOT IN (0, 10, 11, 20), is_garbage = False): {total_available_contracts}"
            )

            total_batches = math.ceil(config.FETCH_LIMIT / config.BATCH_SIZE)
            # Collect futures for async publishing
            publish_futures = []
            processed_contracts = 0
            published_batches = 0
            has_tried_redis_contracts = False
            initial_redis_contract_count = 0
            successfully_truncated_count = 0  # Track successfully truncated contracts
            for batch_num in range(total_batches):
                if processed_contracts >= config.FETCH_LIMIT:
                    logger.info("Reached FETCH_LIMIT, stopping early")
                    break

                logger.info(
                    f"Fetching batch {batch_num + 1}/{total_batches} (last_id={last_id})"
                )

                # Fetch contracts and directory info (filter by type = 1 and status NOT IN (0, 10, 11, 20) and is_garbage = False)
                # 0: Disabled, 10: Unused, 11: Used, 20: In Process, is_garbage = False: Not in trash
                cursor.execute(
                    """
                    SELECT c.id, c.name, c.directory_id, d.name AS directory_name
                    FROM conpass_contract AS c
                    LEFT JOIN conpass_directory AS d ON d.id = c.directory_id
                    WHERE c.type = 1 AND c.status NOT IN (0, 10, 11, 20) AND c.is_garbage = False
                    AND c.id > %s
                    ORDER BY c.id ASC
                    LIMIT %s;
                """,
                    (last_id, config.BATCH_SIZE),
                )

                contracts = cursor.fetchall()
                is_processing_large_contracts = False
                large_contract_ids_from_redis = set()

                if not contracts:
                    # Check Redis for large contracts that were previously excluded
                    logger.info(
                        "No more contracts from DB. Checking Redis for large contracts to retry."
                    )
                    large_contract_ids = get_large_contract_ids_from_redis(redis_client)

                    if large_contract_ids:
                        # Track that we're attempting to process Redis contracts
                        if not has_tried_redis_contracts:
                            has_tried_redis_contracts = True
                            initial_redis_contract_count = len(large_contract_ids)
                            logger.info(
                                f"Found {initial_redis_contract_count} large contracts in Redis. Attempting to process them."
                            )
                        else:
                            # We've already tried processing Redis contracts in this run
                            # Continue processing to allow truncation logic to handle them
                            current_count = len(large_contract_ids)
                            logger.info(
                                f"Retrying {current_count} remaining large contracts from Redis "
                                f"({initial_redis_contract_count - current_count} already processed). "
                                f"Will attempt truncation if needed."
                            )
                        is_processing_large_contracts = True
                        large_contract_ids_from_redis = set(large_contract_ids)
                        # Fetch contracts from DB using the IDs from Redis
                        placeholders = ",".join(["%s"] * len(large_contract_ids))
                        cursor.execute(
                            f"""
                            SELECT c.id, c.name, c.directory_id, d.name AS directory_name
                            FROM conpass_contract AS c
                            LEFT JOIN conpass_directory AS d ON d.id = c.directory_id
                            WHERE c.id IN ({placeholders})
                                AND c.type = 1 AND c.status NOT IN (0, 10, 11, 20) AND c.is_garbage = False;
                            """,
                            large_contract_ids,
                        )
                        contracts = cursor.fetchall()

                        if not contracts:
                            logger.info(
                                "No valid large contracts found in DB. All processed."
                            )
                            disable_scheduler()
                            break
                        else:
                            logger.info(
                                f"Retrieved {len(contracts)} large contracts from DB for retry."
                            )
                    else:
                        logger.info("No more contracts to process.")
                        disable_scheduler()
                        break

                # Update counters
                processed_contracts += len(contracts)

                # Track max/new last_id (only update if not processing large contracts from Redis)
                contract_ids = [c["id"] for c in contracts]
                if not is_processing_large_contracts:
                    batch_max_id = max(contract_ids)
                    max_id_in_run = batch_max_id
                    last_id = batch_max_id

                # Fetch only the latest version of each contract body
                # Using version cast to DECIMAL for correct numeric comparison
                placeholders = ",".join(["%s"] * len(contract_ids))
                cursor.execute(
                    f"""
                    SELECT cb.contract_id, cb.body
                    FROM conpass_contractbody cb
                    INNER JOIN (
                        SELECT contract_id, MAX(CAST(version AS DECIMAL(10,2))) AS max_version
                        FROM conpass_contractbody
                        WHERE contract_id IN ({placeholders})
                        GROUP BY contract_id
                    ) latest ON latest.contract_id = cb.contract_id
                            AND CAST(cb.version AS DECIMAL(10,2)) = latest.max_version;
                    """,
                    contract_ids,
                )
                bodies = cursor.fetchall()
                body_map = {b["contract_id"]: b for b in bodies}

                # Fetch metadata + metakey (filter by mk.type = 1 and md.status = 1)
                # Use string formatting with placeholders for IN clause
                placeholders = ",".join(["%s"] * len(contract_ids))
                cursor.execute(
                    f"""
                    SELECT
                        md.contract_id,
                        mk.name AS key_name,
                        mk.label,
                        md.value,
                        md.date_value
                    FROM conpass_metadata md
                    JOIN conpass_metakey mk ON mk.id = md.key_id
                    WHERE md.contract_id IN ({placeholders})
                        AND mk.type = 1
                        AND md.status = 1;
                    """,
                    contract_ids,
                )

                metadata = cursor.fetchall()

                # Group metadata
                meta_map = {}  # type: ignore
                for m in metadata:
                    cid = m["contract_id"]
                    meta_map.setdefault(cid, []).append(
                        {
                            "key": m["key_name"],
                            "label": m["label"],
                            "value": m["value"]
                            if m["value"] is not None
                            else m["date_value"],
                        }
                    )

                # Construct structured contract JSON
                contracts_json = []
                for contract in contracts:
                    cid = contract["id"]
                    contracts_json.append(
                        {
                            "id": cid,
                            "name": contract["name"],
                            "directory": {
                                "id": contract["directory_id"],
                                "name": contract["directory_name"],
                            },
                            "body": body_map.get(cid, {}).get("body"),
                            "metadata": meta_map.get(cid, []),
                        }
                    )

                # Prepare batch message
                batch_message = {
                    "batch_number": batch_num + 1,
                    "contracts_count": len(contracts_json),
                    "contracts": contracts_json,
                }

                # Serialize with datetime support
                data = json.dumps(
                    batch_message, ensure_ascii=False, cls=DateTimeEncoder
                ).encode("utf-8")
                logger.info(f"Batch size: {len(data)} bytes")

                # Validate message size (Pub/Sub limit is 10MB)
                max_message_size = 10 * 1000 * 1000  # 10MB (10000000 bytes)
                if len(data) > max_message_size:
                    logger.warning(
                        f"Batch {batch_num + 1} exceeds 10MB limit ({len(data)} bytes). "
                        f"Splitting batch to exclude large contracts."
                    )

                    # Split contracts into small and large
                    small_contracts = []  # type: ignore
                    large_contracts = []  # type: ignore

                    # Iterate through contracts and test if they fit in a batch
                    for contract in contracts_json:
                        contract_id = contract["id"]
                        contract_size = calculate_contract_size(contract)

                        # First check if contract alone exceeds limit (with minimal batch overhead)
                        # Estimate overhead: batch structure + some padding
                        estimated_overhead = 200  # bytes for batch structure
                        if contract_size + estimated_overhead > max_message_size:
                            # Contract alone is too large, try to truncate the body
                            logger.warning(
                                f"Contract {contract_id} alone is too large ({contract_size} bytes). "
                                f"Attempting to truncate body."
                            )

                            # Calculate max body size: 10MB - overhead - other contract fields (id, name, directory, metadata)
                            # Estimate other fields size by creating a contract without body
                            contract_without_body = {
                                "id": contract["id"],
                                "name": contract.get("name"),
                                "directory": contract.get("directory"),
                                "metadata": contract.get("metadata", []),
                                "body": "",
                            }
                            other_fields_size = len(
                                json.dumps(
                                    contract_without_body,
                                    ensure_ascii=False,
                                    cls=DateTimeEncoder,
                                ).encode("utf-8")
                            )
                            batch_structure_size = len(
                                json.dumps(
                                    {
                                        "batch_number": 1,
                                        "contracts_count": 1,
                                        "contracts": [],
                                    },
                                    ensure_ascii=False,
                                ).encode("utf-8")
                            )
                            max_body_bytes = (
                                max_message_size
                                - other_fields_size
                                - batch_structure_size
                                - 500
                            )  # 500 bytes safety margin

                            # Safety check: ensure max_body_bytes is reasonable (at least 1000 bytes)
                            if max_body_bytes < 1000:
                                logger.error(
                                    f"Contract {contract_id} has too large non-body fields. "
                                    f"Cannot truncate effectively. max_body_bytes: {max_body_bytes}"
                                )
                                # Mark as large contract and skip
                                large_redis_key = f"{config.REDIS_LARGE_CONTRACT_KEY_PREFIX}{contract_id}"
                                redis_client.set(large_redis_key, contract_size)
                                large_contracts.append(contract_id)
                                continue

                            # Truncate the contract body
                            truncated_contract = truncate_contract_body(
                                contract, max_body_bytes
                            )

                            # Test if truncated contract fits
                            test_single_batch = {
                                "batch_number": batch_num + 1,
                                "contracts_count": 1,
                                "contracts": [truncated_contract],
                            }
                            test_truncated_data = json.dumps(
                                test_single_batch,
                                ensure_ascii=False,
                                cls=DateTimeEncoder,
                            ).encode("utf-8")
                            test_truncated_size = len(test_truncated_data)

                            if test_truncated_size <= max_message_size:
                                # Truncated contract fits, publish it as a single-contract batch
                                try:
                                    future = publisher.publish(
                                        topic_path, data=test_truncated_data
                                    )
                                    message_id = future.result()
                                    logger.info(
                                        f"Published truncated contract {contract_id} as single-contract batch. "
                                        f"Size: {test_truncated_size} bytes, message_id: {message_id}"
                                    )

                                    # Store in truncated_contract Redis key and remove from large_contract key
                                    truncated_redis_key = f"{config.REDIS_TRUNCATED_CONTRACT_KEY_PREFIX}{contract_id}"
                                    large_redis_key = f"{config.REDIS_LARGE_CONTRACT_KEY_PREFIX}{contract_id}"
                                    redis_client.set(
                                        truncated_redis_key, test_truncated_size
                                    )
                                    redis_client.delete(large_redis_key)
                                    logger.info(
                                        f"Contract {contract_id} stored in truncated key: {truncated_redis_key}, "
                                        f"removed from large key: {large_redis_key}"
                                    )

                                    # Track successful truncation
                                    successfully_truncated_count += 1
                                    processed_contracts += 1

                                    # If this contract was from Redis (large contract retry), track it
                                    if contract_id in large_contract_ids_from_redis:
                                        logger.info(
                                            f"Truncated contract {contract_id} was from Redis large contracts. "
                                            f"Successfully processed."
                                        )
                                except Exception as e:
                                    logger.error(
                                        f"Failed to publish truncated contract {contract_id}: {e}"
                                    )
                                    # If publish fails, mark as large contract
                                    large_redis_key = f"{config.REDIS_LARGE_CONTRACT_KEY_PREFIX}{contract_id}"
                                    redis_client.set(large_redis_key, contract_size)
                                    large_contracts.append(contract_id)
                            else:
                                # Even after truncation, contract is too large
                                logger.error(
                                    f"Contract {contract_id} is still too large after truncation "
                                    f"({test_truncated_size} bytes). Storing in Redis."
                                )
                                large_redis_key = f"{config.REDIS_LARGE_CONTRACT_KEY_PREFIX}{contract_id}"
                                redis_client.set(large_redis_key, contract_size)
                                large_contracts.append(contract_id)
                            continue

                        # Test if adding this contract to existing small contracts would exceed the limit
                        test_contracts = small_contracts + [contract]
                        test_batch = {
                            "batch_number": batch_num + 1,
                            "contracts_count": len(test_contracts),
                            "contracts": test_contracts,
                        }
                        test_data = json.dumps(
                            test_batch, ensure_ascii=False, cls=DateTimeEncoder
                        ).encode("utf-8")
                        test_size = len(test_data)

                        if test_size > max_message_size:
                            # Contract would make batch too large, mark it in Redis
                            redis_key = (
                                f"{config.REDIS_LARGE_CONTRACT_KEY_PREFIX}{contract_id}"
                            )
                            redis_client.set(redis_key, contract_size)
                            large_contracts.append(contract_id)
                            logger.warning(
                                f"Contract {contract_id} would exceed batch limit ({contract_size} bytes). "
                                f"Stored in Redis key: {redis_key}"
                            )
                        else:
                            # Contract fits, add it to small contracts
                            small_contracts.append(contract)
                            # If this contract was from Redis (large contract retry), remove it from Redis
                            if contract_id in large_contract_ids_from_redis:
                                redis_key = f"{config.REDIS_LARGE_CONTRACT_KEY_PREFIX}{contract_id}"
                                redis_client.delete(redis_key)
                                logger.info(
                                    f"Contract {contract_id} successfully included in batch. "
                                    f"Removed from Redis key: {redis_key}"
                                )

                    # Update batch message with only small contracts
                    if small_contracts:
                        batch_message = {
                            "batch_number": batch_num + 1,
                            "contracts_count": len(small_contracts),
                            "contracts": small_contracts,
                        }
                        data = json.dumps(
                            batch_message, ensure_ascii=False, cls=DateTimeEncoder
                        ).encode("utf-8")
                        logger.info(
                            f"Split batch: {len(small_contracts)} small contracts, "
                            f"{len(large_contracts)} large contracts excluded. "
                            f"New batch size: {len(data)} bytes"
                        )
                    else:
                        # All contracts are too large, skip this batch
                        logger.error(
                            f"Batch {batch_num + 1}: All contracts are too large. "
                            f"Skipping batch. Large contracts stored in Redis."
                        )
                        continue
                else:
                    # Batch is within size limit, check if any contracts are from Redis and remove them
                    for contract in contracts_json:
                        contract_id = contract["id"]
                        if contract_id in large_contract_ids_from_redis:
                            redis_key = (
                                f"{config.REDIS_LARGE_CONTRACT_KEY_PREFIX}{contract_id}"
                            )
                            redis_client.delete(redis_key)
                            logger.info(
                                f"Contract {contract_id} successfully included in batch. "
                                f"Removed from Redis key: {redis_key}"
                            )

                # Publish to Pub/Sub (async - don't wait for result yet)
                future = publisher.publish(topic_path, data=data)
                publish_futures.append((batch_num + 1, future))
                logger.info(
                    f"Queued batch {batch_num + 1}/{total_batches} for publishing"
                )
                published_batches += 1

            # Wait for all publishes to complete
            logger.info(
                f"Waiting for {len(publish_futures)} batches to be published..."
            )
            for batch_num, future in publish_futures:
                try:
                    message_id = future.result()
                    logger.info(
                        f"Published batch {batch_num}/{total_batches}, message ID: {message_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to publish batch {batch_num}: {e}")

            # Update Redis with new last_id
            redis_client.set(config.REDIS_LAST_ID_KEY, max_id_in_run)
            logger.info(f"Updated last_id in Redis to: {max_id_in_run}")

            # Check if we tried processing large contracts from Redis and if they're all still too large
            if has_tried_redis_contracts:
                remaining_large_contract_ids = get_large_contract_ids_from_redis(
                    redis_client
                )
                remaining_count = len(remaining_large_contract_ids)

                # Calculate how many were removed from Redis (truncated contracts are removed from large_contract key)
                removed_from_redis = initial_redis_contract_count - remaining_count

                if (
                    remaining_count >= initial_redis_contract_count
                    and successfully_truncated_count == 0
                ):
                    # No progress made - all contracts are still too large and none were truncated
                    logger.warning(
                        f"All {initial_redis_contract_count} large contracts from Redis are still too large "
                        f"to process ({remaining_count} remaining, {successfully_truncated_count} truncated). "
                        f"Disabling scheduler to prevent infinite loop."
                    )
                    disable_scheduler()
                    return (
                        f"Processed {published_batches} batches, {processed_contracts} contracts. "
                        f"All large contracts from Redis are still too large. Scheduler disabled.",
                        200,
                    )
                elif remaining_count > 0:
                    logger.info(
                        f"Progress made: {removed_from_redis} contracts removed from Redis "
                        f"({successfully_truncated_count} truncated). "
                        f"{remaining_count} still remaining in Redis."
                    )
                else:
                    logger.info(
                        f"All {initial_redis_contract_count} large contracts from Redis have been processed "
                        f"({successfully_truncated_count} truncated, {removed_from_redis - successfully_truncated_count} included in batches)."
                    )

        return (
            f"Successfully published {published_batches} batches, processed {processed_contracts} contracts",
            200,
        )

    except pymysql.Error as e:
        logger.error(f"Database error: {e}")
        return (f"Database error: {e}", 500)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return (f"Error fetching or publishing data: {e}", 500)

    finally:
        conn.close()
