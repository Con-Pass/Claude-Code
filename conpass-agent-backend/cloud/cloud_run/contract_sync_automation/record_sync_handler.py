import os
import json
import pymysql
import logging
from google.cloud import pubsub_v1
import functions_framework
import datetime
import time
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


publisher = pubsub_v1.PublisherClient()

project_id = os.getenv("GCP_PROJECT", "conpass-agent")
PUBSUB_TOPIC = "generate-embeddings-pubsub-dev"
BATCH_SIZE = 10

# Connection retry defaults can be overridden via env vars for faster tuning
DB_CONNECT_MAX_ATTEMPTS = int(os.getenv("DB_CONNECT_MAX_ATTEMPTS", "3"))
DB_CONNECT_BACKOFF_SECONDS = float(os.getenv("DB_CONNECT_BACKOFF_SECONDS", "1.5"))

# Pub/Sub setup
topic_path = publisher.topic_path(project_id, PUBSUB_TOPIC)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that converts datetime/date objects to strings."""

    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)


# Database setup (use env vars)
def get_mysql_connection():
    """
    Create and return a MySQL database connection using environment variables.

    Returns:
        pymysql.Connection: Database connection object, or None if connection fails.
    """
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    database = os.getenv("DB_NAME")
    port = 3306

    # Validate required environment variables
    if not all([host, user, password, database]):
        logger.error(
            "Missing required database environment variables: DB_HOST, DB_USER, DB_PASS, DB_NAME"
        )
        return None

    attempts = max(1, DB_CONNECT_MAX_ATTEMPTS)
    for attempt in range(1, attempts + 1):
        try:
            connection = pymysql.connect(
                host=host,
                user=user,
                password=password,
                database=database,
                port=port,
                connect_timeout=15,
                cursorclass=pymysql.cursors.DictCursor,
            )
            if attempt > 1:
                logger.info("Database connection succeeded on retry %d", attempt)
            return connection
        except pymysql.Error as e:
            logger.error(
                "Database connection failed (attempt %d/%d): %s",
                attempt,
                attempts,
                str(e),
            )
            if attempt == attempts:
                return None
            time.sleep(DB_CONNECT_BACKOFF_SECONDS * (2 ** (attempt - 1)))
        except Exception as e:
            logger.error(
                "Unexpected error during connection (attempt %d/%d): %s",
                attempt,
                attempts,
                str(e),
            )
            if attempt == attempts:
                return None
            time.sleep(DB_CONNECT_BACKOFF_SECONDS * (2 ** (attempt - 1)))


@functions_framework.http
def records_sync_handler(request):
    """Handles new or updated contracts by fetching and publishing delta data."""
    try:
        event = request.get_json(silent=True)
        if not event or "contract_ids" not in event:
            return ("Missing 'contract_ids' in request body", 400)

        contract_ids = event["contract_ids"]
        if not isinstance(contract_ids, list):
            contract_ids = [contract_ids]

        event_type = event.get("event_type", "updated")
        logger.info(
            f"Received sync event (type={event_type}) for contracts: {contract_ids}"
        )

        # For deleted events, skip database calls and use contract_ids directly
        if event_type == "deleted":
            contracts_json = None  # Will use contract_ids directly in batch message
        else:
            # For non-deleted events, fetch data from database
            conn = get_mysql_connection()
            if not conn:
                return ("Database connection failed", 500)

            try:
                with conn.cursor() as cursor:
                    # --- Fetch contracts (filtered) ---
                    # Excluded: 0: Disabled, 10: Unused, 11: Used, 20: In Process, is_garbage = False: Not in trash
                    placeholders = ",".join(["%s"] * len(contract_ids))
                    cursor.execute(
                        f"""
                        SELECT c.id, c.name, c.directory_id, d.name AS directory_name
                        FROM conpass_contract AS c
                        LEFT JOIN conpass_directory AS d ON d.id = c.directory_id
                        WHERE c.id IN ({placeholders})
                            AND c.type = 1 AND c.status NOT IN (0, 10, 11, 20) AND c.is_garbage = False;
                        """,
                        contract_ids,
                    )
                    contracts = cursor.fetchall()
                    if not contracts:
                        return ("No matching active contracts found", 404)

                    # --- Fetch latest body version ---
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

                    # --- Fetch metadata (active only) ---
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

                    meta_map = {}  # type: ignore
                    for m in metadata:
                        cid = m["contract_id"]
                        meta_map.setdefault(cid, []).append(
                            {
                                "key": m["key_name"],
                                "label": m["label"],
                                "value": m["value"] or m["date_value"],
                            }
                        )

                    # --- Build message payload ---
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
            finally:
                conn.close()

        # Chunk into batches (works for both deleted and non-deleted events)
        if event_type == "deleted":
            # For deleted events, batch the contract_ids directly
            total_contracts = len(contract_ids)
        else:
            # For non-deleted events, use contracts_json
            total_contracts = len(contracts_json)

        total_batches = max(1, math.ceil(total_contracts / BATCH_SIZE))
        publish_futures = []
        timestamp = datetime.datetime.now().isoformat()

        for batch_num in range(total_batches):
            start = batch_num * BATCH_SIZE
            end = start + BATCH_SIZE

            if event_type == "deleted":
                batch_contract_ids = contract_ids[start:end]
                # create the message payload for the batch
                batch_message = {
                    "batch_number": batch_num + 1,
                    "contracts_count": len(batch_contract_ids),
                    "contract_ids": batch_contract_ids,
                    "event_type": event_type,
                    "timestamp": timestamp,
                }
                batch_size = len(batch_contract_ids)
            else:
                batch_contracts = contracts_json[start:end]
                # create the message payload for the batch
                batch_message = {
                    "batch_number": batch_num + 1,
                    "contracts_count": len(batch_contracts),
                    "contracts": batch_contracts,
                    "event_type": event_type,
                    "timestamp": timestamp,
                }
                batch_size = len(batch_contracts)

            data = json.dumps(
                batch_message, ensure_ascii=False, cls=DateTimeEncoder
            ).encode("utf-8")
            logger.info(
                "Prepared sync batch %d/%d (items=%d, size=%d bytes)",
                batch_num + 1,
                total_batches,
                batch_size,
                len(data),
            )
            logger.info(
                f"Published Data: {json.dumps(batch_message, ensure_ascii=False, cls=DateTimeEncoder)}"
            )
            future = publisher.publish(topic_path, data=data)
            publish_futures.append((batch_num + 1, future))

        # Wait for all publish futures
        for batch_num, future in publish_futures:
            try:
                message_id = future.result()
                logger.info(
                    "Published sync batch %d/%d, message_id=%s",
                    batch_num,
                    total_batches,
                    message_id,
                )
            except Exception as pub_err:
                logger.error(
                    "Failed to publish sync batch %d/%d: %s",
                    batch_num,
                    total_batches,
                    pub_err,
                )

        return (
            f"Published {total_contracts} contract updates in {total_batches} batches",
            200,
        )

    except Exception as e:
        logger.error(f"Error processing sync event: {e}", exc_info=True)
        return (f"Error processing sync event: {e}", 500)
