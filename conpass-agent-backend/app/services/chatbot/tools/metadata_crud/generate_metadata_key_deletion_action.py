from typing import List, Union
from app.core.logging_config import get_logger
from app.services.conpass_api_service import ConpassApiService
from app.schemas.metadata_crud import (
    DeleteMetadataKeyAction,
    DeleteMetadataKey,
    MetadataActionError
)
from app.services.chatbot.tools.metadata_crud.error_handling import (
    ValidationError,
    ApiError,
    NotFoundError,
    handle_api_response,
    normalize
)
from app.utils.crud_metadata_hash_utils import generate_jwt_token

logger = get_logger(__name__)

# API URLs for metadata key deletion actions
CONFIRMATION_API_URL = "/metadata/delete-key"
CANCEL_API_URL = "/metadata/delete-key/cancel"

# Static title for delete metadata key actions
DELETE_METADATA_KEY_TITLE = "Delete Metadata Key"


async def generate_metadata_key_deletion_action(
    conpass_api_service: ConpassApiService,
    keys: List[DeleteMetadataKey]
) -> Union[DeleteMetadataKeyAction, MetadataActionError]:
    """
    Delete FREE/custom metadata keys at the account level.

    This function validates inputs and returns an action template for user approval.
    After approval, the execution endpoint will delete the MetaKeys via POST /setting/meta/update.

    Args:
        conpass_api_service: ConPass API service instance
        keys: List of DeleteMetadataKey objects containing key_id and key_name pairs

    Returns:
        DeleteMetadataKeyAction with validation results and action details, or MetadataActionError
    """
    logger.info(f"[DELETE_METADATA_KEY] Called with keys='{keys}'")

    # Normalize and validate input
    try:
        logger.info("[DELETE_METADATA_KEY] Converting keys to DeleteMetadataKey models...")
        normalized_keys = normalize(keys)
        
        if not isinstance(normalized_keys, list) or len(normalized_keys) == 0:
            logger.error("[DELETE_METADATA_KEY] Empty or invalid keys list")
            return MetadataActionError(
                is_error=True,
                error_code="INVALID_INPUT",
                error_message="At least one metadata key is required for deletion.",
                details={
                    "keys": keys,
                    "title": DELETE_METADATA_KEY_TITLE
                }
            )
        
        # Check for duplicate key_ids
        key_ids = [k.get("key_id") for k in normalized_keys]
        if len(key_ids) != len(set(key_ids)):
            logger.error("[DELETE_METADATA_KEY] Duplicate key_ids found")
            return MetadataActionError(
                is_error=True,
                error_code="DUPLICATE_KEYS",
                error_message="Duplicate metadata key IDs are not allowed.",
                details={
                    "keys": normalized_keys,
                    "title": DELETE_METADATA_KEY_TITLE
                }
            )
        
    except ValidationError as e:
        logger.error(f"[DELETE_METADATA_KEY] Validation error: {e.message}")
        return MetadataActionError(
            is_error=True,
            error_message=(
                f"Invalid metadata key data: {e.message}. "
                f"Details: {e.details if e.details else 'No additional details'}."
            ),
            details={
                "keys": keys,
                "title": DELETE_METADATA_KEY_TITLE
            }
        )

    # Verify all keys exist
    logger.debug("[DELETE_METADATA_KEY] Verifying keys exist")
    try:
        keys_response = await conpass_api_service.get_free_metadata_keys()
        logger.info(
            f"[DELETE_METADATA_KEY] FREE keys response: "
            f"status={keys_response.status}, has_data={keys_response.data is not None}"
        )

        try:
            response_data = handle_api_response(
                keys_response,
                "verifying metadata keys exist",
            )
        except (ApiError, NotFoundError) as e:
            logger.error(f"[DELETE_METADATA_KEY] API error: {e.message}")
            return MetadataActionError(
                is_error=True,
                error_message=(
                    f"Failed to verify metadata keys: {e.message}. "
                    f"Cannot proceed with deletion. "
                    f"{'This may be a temporary issue, please try again.' if isinstance(e, ApiError) and e.recoverable else ''}"
                ),
                details={
                    "keys": normalized_keys,
                    "title": DELETE_METADATA_KEY_TITLE
                }
            )

        # --- Extract existing keys ---
        existing_keys = []
        if isinstance(response_data, list):
            existing_keys = response_data
        elif isinstance(response_data, dict):
            if "response" in response_data:
                existing_keys = response_data.get("response", [])
            elif "data" in response_data:
                existing_keys = response_data.get("data", [])

        if not isinstance(existing_keys, list):
            error_msg = (
                f"Invalid response format from API: expected list of keys, got {type(existing_keys).__name__}. "
                f"Cannot verify if metadata keys exist."
            )
            logger.error(f"[DELETE_METADATA_KEY] {error_msg}")
            return MetadataActionError(
                is_error=True,
                error_message=error_msg,
                details={
                    "keys": normalized_keys,
                    "title": DELETE_METADATA_KEY_TITLE
                }
            )

        # --- Build existing keys map ---
        existing_keys_map = {}
        for key in existing_keys:
            if isinstance(key, dict) and "id" in key:
                existing_keys_map[key["id"]] = key

        # --- Verify all keys to delete exist ---
        not_found_keys = []
        for key_data in normalized_keys:
            key_id = key_data.get("key_id")
            if key_id not in existing_keys_map:
                not_found_keys.append(key_data)
                logger.warning(f"[DELETE_METADATA_KEY] Key not found: id={key_id}, name='{key_data.get('key_name')}'")

        if not_found_keys:
            not_found_names = [k.get("key_name") for k in not_found_keys]
            error_msg = (
                f"The following metadata key(s) were not found: {', '.join(not_found_names)}. "
                f"Please verify the key IDs and try again."
            )
            logger.error(f"[DELETE_METADATA_KEY] {error_msg}")
            return MetadataActionError(
                is_error=True,
                error_code="KEYS_NOT_FOUND",
                error_message=error_msg,
                details={
                    "not_found_keys": not_found_keys,
                    "keys": normalized_keys,
                    "title": DELETE_METADATA_KEY_TITLE
                }
            )

        logger.info(f"[DELETE_METADATA_KEY] All {len(normalized_keys)} key(s) verified successfully")

    except ValidationError as e:
        logger.error(f"[DELETE_METADATA_KEY] Validation error: {e.message}")
        return MetadataActionError(
            is_error=True,
            error_message=(
                f"Validation error: {e.message}. "
                f"Details: {e.details if e.details else 'No additional details'}."
            ),
            details={
                "keys": normalized_keys,
                "title": DELETE_METADATA_KEY_TITLE
            }
        )
    except (ApiError, NotFoundError) as e:
        logger.error(f"[DELETE_METADATA_KEY] API error: {e.message}")
        return MetadataActionError(
            is_error=True,
            error_message=(
                f"Error verifying metadata keys: {e.message}. "
                f"Cannot proceed with deletion. "
                f"{'This may be a temporary issue, please try again.' if isinstance(e, ApiError) and e.recoverable else ''}"
            ),
            details={
                "keys": normalized_keys,
                "title": DELETE_METADATA_KEY_TITLE
            }
        )
    except Exception as e:
        error_msg = (
            f"Unexpected error verifying metadata keys: {str(e)}. "
            f"Error type: {type(e).__name__}. "
            f"Cannot proceed with deletion."
        )
        logger.exception(f"[DELETE_METADATA_KEY] {error_msg}")
        return MetadataActionError(
            is_error=True,
            error_message=error_msg,
            details={
                "keys": normalized_keys,
                "title": DELETE_METADATA_KEY_TITLE
            }
        )

    # --- All validations passed - return action template ---
    logger.info(
        f"[DELETE_METADATA_KEY] All validations passed. Creating action template for {len(normalized_keys)} metadata key(s)"
    )

    # --- Convert to DeleteMetadataKey objects ---
    validated_keys_action = [
        DeleteMetadataKey(key_id=k.get("key_id"), key_name=k.get("key_name"))
        for k in normalized_keys
    ]

    # --- Generate JWT token ---
    hashed_metadata_action = generate_jwt_token(
        action=DeleteMetadataKeyAction(
            keys=validated_keys_action,
            title=DELETE_METADATA_KEY_TITLE,
            confirmation_api_url=CONFIRMATION_API_URL,
            cancel_api_url=CANCEL_API_URL,
            status="pending",
            error_message=None
        )
    )

    return DeleteMetadataKeyAction(
        keys=validated_keys_action,
        title=DELETE_METADATA_KEY_TITLE,
        confirmation_api_url=CONFIRMATION_API_URL,
        cancel_api_url=CANCEL_API_URL,
        status="pending",
        error_message=None,
        jwt_token=hashed_metadata_action
    )
