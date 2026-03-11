import os
import json
import logging
import hashlib
import base64
from datetime import datetime

from google.cloud import pubsub_v1
from redis import Redis
import functions_framework
from typing import Optional

# ---------- Configuration ----------
GCP_PROJECT = os.getenv("GCP_PROJECT", "conpass-agent")
MAIN_TOPIC = os.getenv("MAIN_TOPIC", "conpass-agent-pubsub")  # publish back here
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MAX_DLQ_RETRY = int(os.getenv("MAX_DLQ_RETRY", "3"))
BASE_DELAY_SECONDS = int(os.getenv("BASE_DELAY_SECONDS", "60"))
MAX_DELAY_SECONDS = int(os.getenv("MAX_DELAY_SECONDS", "600"))
REDIS_TTL_SECONDS = int(os.getenv("REDIS_TTL_SECONDS", str(7 * 24 * 3600)))
ARCHIVE_TTL_SECONDS = int(os.getenv("ARCHIVE_TTL_SECONDS", str(30 * 24 * 3600)))
ATTEMPTS_KEY_PREFIX = "dlq_attempts:"  # dlq_attempts:<hash> -> integer
PAYLOAD_KEY_PREFIX = "dlq_payload:"  # dlq_payload:<hash> -> raw base64 JSON
ARCHIVE_KEY_PREFIX = "dlq_archive:"  # dlq_archive:<hash> -> metadata + payload
PROCESSED_MESSAGE_KEY_PREFIX = (
    "processed_message:"  # processed_message:<messageId> -> metadata
)
PROCESSING_LOCK_KEY_PREFIX = "processing_lock:"  # processing_lock:<hash> -> lock info
LOCK_TTL_SECONDS = 300  # 5 minutes - prevents stuck locks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pub/Sub publisher
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(GCP_PROJECT, MAIN_TOPIC)


# Redis client
def get_redis_client() -> Optional[Redis]:
    try:
        # Redis URL may be like redis://:password@host:port/db
        return Redis.from_url(REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.warning("Failed to create Redis client: %s", e)
        return None


# compute stable hash for the incoming base64 message body
def compute_payload_hash(payload_b64: str) -> str:
    # Use SHA256 of the raw bytes
    raw = base64.b64decode(payload_b64)
    h = hashlib.sha256(raw).hexdigest()
    return h


def parse_pubsub_push(request_json: dict):
    """
    Parse a Pub/Sub push request format:
    {
        "message": {
            "data": "<base64-encoded payload>",
            "attributes": { ... },
            "messageId": "...",
            "publishTime": "..."
        },
        "subscription": "projects/.../subscriptions/..."
    }
    """
    msg = request_json.get("message")
    if not msg:
        raise ValueError("No 'message' in request body")
    data_b64 = msg.get("data", "")
    attributes = msg.get("attributes", {}) or {}
    message_id = msg.get("messageId") or ""
    publish_time = msg.get("publishTime") or ""
    return data_b64, attributes, message_id, publish_time


def compute_backoff_seconds(attempt: int) -> int:
    # Example: base * (attempt ** 2) with cap
    delay = BASE_DELAY_SECONDS * (attempt**2)
    if delay > MAX_DELAY_SECONDS:
        delay = MAX_DELAY_SECONDS
    return int(delay)


def archive_failed_batch(
    redis_client: Optional[Redis],
    payload_b64: str,
    payload_hash: str,
    attempts: int,
    last_error: str = "",
):
    meta = {
        "payload_hash": payload_hash,
        "attempts": attempts,
        "archived_at": datetime.now().isoformat() + "Z",
        "last_error": last_error,
        "payload_b64": payload_b64,
    }
    key = ARCHIVE_KEY_PREFIX + payload_hash
    try:
        if redis_client:
            redis_client.setex(key, ARCHIVE_TTL_SECONDS, json.dumps(meta))
        logger.error("Archived DLQ payload %s (attempts=%d)", payload_hash, attempts)
    except Exception as e:
        logger.exception("Failed to archive DLQ payload to Redis: %s", e)
        # still continue


def ensure_payload_saved(
    redis_client: Optional[Redis], payload_b64: str, payload_hash: str
):
    """
    Save the payload base64 into Redis if not already present.
    """
    if not redis_client:
        return
    pkey = PAYLOAD_KEY_PREFIX + payload_hash
    try:
        # set only if not exists
        was_set = redis_client.setnx(pkey, payload_b64)
        # always update TTL to keep it alive while attempts ongoing
        redis_client.expire(pkey, REDIS_TTL_SECONDS)
        return was_set
    except Exception as e:
        logger.warning("Redis setnx failed for payload: %s", e)
        return False


def increment_attempts(redis_client: Optional[Redis], payload_hash: str) -> int:
    """
    Atomically increment attempt counter and set TTL.
    Returns the new attempt count.
    """
    key = ATTEMPTS_KEY_PREFIX + payload_hash
    try:
        if redis_client:
            attempts = redis_client.incr(key)
            redis_client.expire(key, REDIS_TTL_SECONDS)
            return int(attempts)
    except Exception as e:
        logger.warning("Failed to increment attempts in Redis: %s", e)
    # If Redis not available, return 1 (best-effort)
    return 1


def is_message_processed(redis_client: Optional[Redis], message_id: str) -> bool:
    """
    Check if message was already processed.
    Returns True if message was processed, False otherwise.
    """
    if not message_id or not redis_client:
        return False
    key = PROCESSED_MESSAGE_KEY_PREFIX + message_id
    try:
        return redis_client.exists(key) > 0
    except Exception as e:
        logger.warning("Failed to check if message is processed: %s", e)
        return False


def mark_message_processed(
    redis_client: Optional[Redis], message_id: str, payload_hash: str
) -> bool:
    """
    Mark message as processed.
    Returns True if successfully marked, False otherwise.
    """
    if not message_id or not redis_client:
        return False
    key = PROCESSED_MESSAGE_KEY_PREFIX + message_id
    value = json.dumps(
        {
            "processed_at": datetime.now().isoformat() + "Z",
            "payload_hash": payload_hash,
            "message_id": message_id,
        }
    )
    try:
        redis_client.setex(key, REDIS_TTL_SECONDS, value)
        return True
    except Exception as e:
        logger.warning("Failed to mark message as processed: %s", e)
        return False


def acquire_processing_lock(
    redis_client: Optional[Redis], payload_hash: str, message_id: str
) -> bool:
    """
    Acquire distributed lock for processing payload.
    Uses Redis SETNX for atomic lock acquisition.
    Returns True if lock acquired, False otherwise.
    """
    if not payload_hash or not redis_client:
        return False
    key = PROCESSING_LOCK_KEY_PREFIX + payload_hash
    value = json.dumps(
        {"message_id": message_id, "locked_at": datetime.now().isoformat() + "Z"}
    )
    try:
        # SETNX: set if not exists (atomic operation)
        was_set = redis_client.setnx(key, value)
        if was_set:
            # Set TTL to prevent stuck locks
            redis_client.expire(key, LOCK_TTL_SECONDS)
            return True
        return False
    except Exception as e:
        logger.warning("Failed to acquire processing lock: %s", e)
        return False


def release_processing_lock(redis_client: Optional[Redis], payload_hash: str) -> bool:
    """
    Release distributed lock.
    Returns True if successfully released, False otherwise.
    """
    if not payload_hash or not redis_client:
        return False
    key = PROCESSING_LOCK_KEY_PREFIX + payload_hash
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        logger.warning("Failed to release processing lock: %s", e)
        return False


@functions_framework.http
def dlq_processor(request):
    """
    HTTP Cloud Function that handles Pub/Sub push requests for the DLQ topic.
    Expects the standard Pub/Sub push JSON. Returns 200 on success (ack).
    """
    redis_client = None
    payload_hash = None
    message_id = None

    try:
        request_json = request.get_json(silent=True)
        if not request_json:
            logger.error("Request body not JSON or empty")
            # Return 200 to ack malformed messages (prevent DLQ clutter)
            return ("Bad Request - expected JSON body", 200)

        data_b64, attributes, message_id, publish_time = parse_pubsub_push(request_json)
        if not data_b64:
            logger.warning("Empty message.data in DLQ message, acking and skipping")
            return ("OK - empty payload", 200)

        logger.info(
            "Received DLQ message: messageId=%s, publishTime=%s",
            message_id,
            publish_time,
        )
        logger.info("Attributes: %s", attributes)

        # Get Redis client
        redis_client = get_redis_client()

        # Check messageId idempotency (prevent duplicate processing of same message)
        if is_message_processed(redis_client, message_id):
            logger.info("Message %s already processed, skipping", message_id)
            return ("Already processed", 200)

        # Compute payload hash
        payload_hash = compute_payload_hash(data_b64)

        # Try to acquire processing lock (prevent concurrent processing of same payload)
        lock_acquired = acquire_processing_lock(redis_client, payload_hash, message_id)
        if not lock_acquired:
            logger.info(
                "Payload %s is being processed by another instance, skipping message %s",
                payload_hash,
                message_id,
            )
            return ("Another instance processing", 200)

        try:
            # Ensure payload saved
            ensure_payload_saved(redis_client, data_b64, payload_hash)

            # Increment attempts
            attempts = increment_attempts(redis_client, payload_hash)
            logger.info(
                "DLQ payload %s attempts=%d (messageId=%s)",
                payload_hash,
                attempts,
                message_id,
            )

            # Check max retries
            if attempts > MAX_DLQ_RETRY:
                archive_failed_batch(
                    redis_client, data_b64, payload_hash, attempts, last_error=""
                )
                logger.error(
                    "DLQ payload %s exceeded max retries (%d). Archived.",
                    payload_hash,
                    MAX_DLQ_RETRY,
                )
                return ("Archived - exceeded retries", 200)

            # Republish immediately (no sleep - prevents function timeout)
            payload_bytes = base64.b64decode(data_b64)
            publish_future = publisher.publish(
                topic_path,
                data=payload_bytes,
                dlq_attempts=str(attempts),
                dlq_payload_hash=payload_hash,
            )
            message_id_out = publish_future.result(timeout=60)
            logger.info(
                "Republished DLQ payload %s to topic %s message_id=%s (attempts=%d)",
                payload_hash,
                MAIN_TOPIC,
                message_id_out,
                attempts,
            )

            # Mark message as processed
            mark_message_processed(redis_client, message_id, payload_hash)

            # Extend TTL to keep metadata for some time after republish
            try:
                if redis_client:
                    redis_client.expire(
                        ATTEMPTS_KEY_PREFIX + payload_hash, REDIS_TTL_SECONDS
                    )
                    redis_client.expire(
                        PAYLOAD_KEY_PREFIX + payload_hash, REDIS_TTL_SECONDS
                    )
            except Exception:
                pass

            return ("Republished", 200)

        finally:
            # Always release lock, even on error
            if payload_hash:
                release_processing_lock(redis_client, payload_hash)

    except Exception as exc:
        logger.exception("Unhandled error in DLQ processor: %s", exc)
        # Release lock if we have payload_hash
        if payload_hash and redis_client:
            try:
                release_processing_lock(redis_client, payload_hash)
            except Exception:
                pass
        # Return 500 to trigger retry (only for unexpected errors)
        return (f"Internal error: {exc}", 500)
