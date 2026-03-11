from typing import List
from app.core.logging_config import get_logger
from app.services.conpass_api_service import ConpassApiService
from app.schemas.metadata_crud import (
    CreateMetadataKeyAction,
    CreateMetadataKey,
    MetadataActionError
)
from app.services.chatbot.tools.metadata_crud.error_handling import (
    ValidationError,
    ApiError,
    NotFoundError,
    handle_api_response, validate_list_of_metadata_key_field,
    normalize,
)
from app.utils.crud_metadata_hash_utils import generate_jwt_token

logger = get_logger(__name__)

# API URLs for metadata key creation actions
CONFIRMATION_API_URL = "/metadata/create-key"
CANCEL_API_URL = "/metadata/create-key/cancel"

# Static title for create metadata key actions
CREATE_METADATA_KEY_TITLE = "Create Metadata Key"


async def generate_metadata_key_creation_action(
    conpass_api_service: ConpassApiService,
    key_names: List[CreateMetadataKey],
) -> CreateMetadataKeyAction | MetadataActionError:
    """
    Create a new FREE/custom metadata key at the account level.

    This function validates inputs and returns an action template for user approval.
    After approval, the execution endpoint will create the MetaKey via POST /setting/meta/update.
    The key will always be created with account-level visibility enabled.

    Note: To enable this key for a directory, use update_directory_metadata_visibility separately.

    Args:
        conpass_api_service: ConPass API service instance
        key_names: List of CreateMetadataKey objects containing the names of keys to create (e.g., [{name: X}...])

    Returns:
        CreateMetadataKeyAction with validation results and action details
    """
    logger.info(f"[CREATE_METADATA_KEY] Called with name='{key_names}'")
    # Validate name
    try:
        logger.info("[CREATE_METADATA_KEY] Converting key_names to CreateMetadataKey models...")
        # Converting string literal to appropriate python
        normalized_key_names = normalize(key_names)
        name_list = [di.get("name") for di in normalized_key_names]

        if len(name_list) != len(set(name_list)):
            logger.error("[CREATE_METADATA_KEY] duplicate keys found")
            return MetadataActionError(
                is_error=True,
                error_code="DUPLICATE_KEYS",
                error_message=(
                    "Duplicate metadata key names are not allowed."
                ),
                details={
                    "key_names": normalized_key_names,
                    "title": CREATE_METADATA_KEY_TITLE

                }

            )
        validated_names = validate_list_of_metadata_key_field(value=name_list)
    except ValidationError as e:
        logger.info(f"[CREATE_METADATA_KEY] Validation error: {e.message}")
        return MetadataActionError(
            is_error=True,
            error_message=(
                f"Invalid metadata key name: {e.message}. "
                f"Details: {e.details if e.details else 'No additional details'}."
            ),
            details={
                "key_names": key_names,
                "title": CREATE_METADATA_KEY_TITLE

            }
        )

    # Check if a FREE key with the same name already exists
    logger.info(
        f"[CREATE_METADATA_KEY] Checking for existing FREE metadata keys with names '{validated_names}'"
    )
    logger.debug("[CREATE_METADATA_KEY] Calling get_free_metadata_keys API")
    try:
        # --- Fetching Free Metadata Keys ---
        keys_response = await conpass_api_service.get_free_metadata_keys()
        logger.info(
            f"[CREATE_METADATA_KEY] FREE keys check response: "
            f"status={keys_response.status}, has_data={keys_response.data is not None}"
        )
        try:
            response_data = handle_api_response(
                keys_response,
                "checking for existing FREE metadata keys",
            )
        except (ApiError, NotFoundError) as e:
            # If we can't check for duplicates, we should fail rather than silently continue
            logger.error(f"[CREATE_METADATA_KEY] API error checking for duplicates: {e.message}")
            return MetadataActionError(
                is_error=True,
                details={
                    "key_names": normalized_key_names,
                    "title": CREATE_METADATA_KEY_TITLE
                },
                error_message=(
                    f"Failed to check for existing metadata keys: {e.message}. "
                    f"Cannot proceed with creation as duplicate check is required. "
                    f"{'This may be a temporary issue, please try again.' if isinstance(e, ApiError) and e.recoverable else ''}"
                ),
            )

        # --- Checking for Existing Keys ----
        existing_keys = []
        if isinstance(response_data, list):
            existing_keys = response_data
        elif isinstance(response_data, dict):
            # Handle wrapped response
            if "response" in response_data:
                existing_keys = response_data.get("response", [])
            elif "data" in response_data:
                existing_keys = response_data.get("data", [])

        if not isinstance(existing_keys, list):
            error_msg = (
                f"Invalid response format from API: expected list of keys, got {type(existing_keys).__name__}. "
                f"Cannot verify if metadata key already exists."
            )
            logger.error(f"[CREATE_METADATA_KEY] {error_msg}")
            return MetadataActionError(
                is_error=True,
                details={
                    "key_names": normalized_key_names,
                    "title": CREATE_METADATA_KEY_TITLE
                },
                error_message=error_msg,
            )

        # --- Checking Key Limits ---
        if len(existing_keys) + len(validated_names) > 10:
            remaining_slots = 10 - len(existing_keys)
            logger.error(
                f"[CREATE_METADATA_KEY] Total key limit would be exceeded: "
                f"{len(existing_keys)} existing + {len(validated_names)} new = "
                f"{len(existing_keys) + len(validated_names)} > 10"
            )
            return MetadataActionError(
                is_error=True,
                details={
                    "key_names": normalized_key_names,
                    "title": CREATE_METADATA_KEY_TITLE
                },

                error_code="KEY_LIMIT_EXCEEDED",
                error_message=(
                    f"Sorry, you can only create {remaining_slots} keys now."
                    if remaining_slots > 0
                    else "You cannot create any more keys. System key slots are currently full."
                )
            )

        # --- Checking for Duplicates ---
        existing_keys_set = set()
        for key in existing_keys:
            if isinstance(key, dict) and "name" in key:
                existing_keys_set.add(key["name"])
            else:
                logger.warning(
                    f"[CREATE_METADATA_KEY] Skipping invalid key: expected dict, got {type(key).__name__}"
                )

        for validated_name in validated_names:
            logger.debug(
                f"[CREATE_METADATA_KEY] Checking {len(existing_keys)} existing FREE keys "
                f"for duplicate name '{validated_name}'"
            )
            if validated_name in existing_keys_set:
                logger.warning(
                    f"[CREATE_METADATA_KEY] Duplicate found: A FREE metadata key with name '{validated_name}'"
                    f"already exists"
                )
                return MetadataActionError(
                    is_error=True,
                    details={
                    "key_names": normalized_key_names,
                    "title": CREATE_METADATA_KEY_TITLE
                },
                    error_message=(
                        f"A metadata key with name '{validated_name}' already exists "
                        f"Please use a different name or update the existing key."
                    ),
                )

            logger.info(
                f"[CREATE_METADATA_KEY] No existing FREE metadata key found with name '{validated_name}'"
            )

    except ValidationError as e:
        logger.error(f"[CREATE_METADATA_KEY] Validation error: {e.message}")
        return MetadataActionError(
            is_error=True,
            details={
                    "key_names": normalized_key_names,
                    "title": CREATE_METADATA_KEY_TITLE
                },
            error_message=(
                f"Validation error: {e.message}. "
                f"Details: {e.details if e.details else 'No additional details'}."
            ),
        )
    except (ApiError, NotFoundError) as e:
        logger.error(f"[CREATE_METADATA_KEY] API error: {e.message}")
        return MetadataActionError(
            is_error=True,
            details={
                    "key_names": normalized_key_names,
                    "title": CREATE_METADATA_KEY_TITLE
                },
            error_message=(
                f"Error checking for existing metadata keys: {e.message}. "
                f"Cannot proceed with creation. "
                f"{'This may be a temporary issue, please try again.' if isinstance(e, ApiError) and e.recoverable else ''}"
            ),
        )
    except Exception as e:
        error_msg = (
            f"Unexpected error checking for existing metadata keys: {str(e)}. "
            f"Error type: {type(e).__name__}. "
            f"Cannot proceed with creation."
        )
        logger.exception(f"[CREATE_METADATA_KEY] {error_msg}")
        return MetadataActionError(
            is_error=True,
            details={
                    "key_names": normalized_key_names,
                    "title": CREATE_METADATA_KEY_TITLE
                },
            error_message=error_msg,
        )

    # --- All validations passed - return action template ---
    logger.info(
        f"[CREATE_METADATA_KEY] All validations passed. Creating action template for metadata key '{validated_names}'"
    )

    # --- Generating Hash and Finalizing Action Template
    validated_names_action = [
        CreateMetadataKey(name=name)
        for name in validated_names
    ]

    hashed_metadata_action = generate_jwt_token(
        action=CreateMetadataKeyAction(
            names=validated_names_action,
            title=CREATE_METADATA_KEY_TITLE,
            confirmation_api_url=CONFIRMATION_API_URL,
            cancel_api_url=CANCEL_API_URL,
            status="pending",
            error_message=None
        )
    )

    return CreateMetadataKeyAction(
        names=validated_names_action,
        title=CREATE_METADATA_KEY_TITLE,
        confirmation_api_url=CONFIRMATION_API_URL,
        cancel_api_url=CANCEL_API_URL,
        status="pending",
        error_message=None,
        jwt_token=hashed_metadata_action
    )
