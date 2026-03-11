from app.core.logging_config import get_logger
from app.services.conpass_api_service import ConpassApiService
from app.schemas.metadata_crud import UpdateMetadataKeyAction, MetadataActionError
from app.services.chatbot.tools.metadata_crud.error_handling import (
    ValidationError,
    ApiError,
    NotFoundError,
    validate_string_field,
    handle_api_response,
)
from app.utils.crud_metadata_hash_utils import generate_jwt_token

logger = get_logger(__name__)

# API URLs for metadata key creation actions
CONFIRMATION_API_URL = "/metadata/update-key"
CANCEL_API_URL = "/metadata/update-key/cancel"

# Static title for create metadata key actions
UPDATE_METADATA_KEY_TITLE = "Update Metadata Key"


async def generate_metadata_key_update_action(
    conpass_api_service: ConpassApiService,
    current_name: str,
    new_name: str,
) -> UpdateMetadataKeyAction | MetadataActionError:
    """
    Update an existing FREE/custom metadata key at the account level.

    This function validates inputs and returns an action template for user approval.
    After approval, the execution endpoint will update the MetaKey via
    POST /setting/meta/update.

    The metadata key remains account-level visible. Any directory-level visibility
    changes must be handled separately using update_directory_metadata_visibility.

    Args:
         conpass_api_service: ConPass API service instance
         current_name: Current name of the metadata key to update (max 255 characters)
         new_name: New display name for the metadata key (max 255 characters)

    Returns:
         UpdateMetadataKeyAction with validation results and action details
    """
    logger.info(
        f"[UPDATE_METADATA_KEY] Called with current_name='{current_name}', new_name='{new_name}'"
    )

    # # Validate current_name
    # try:
    #     validated_current_name = validate_string_field(
    #         current_name, "current_name", max_length=255, allow_empty=False
    #     )
    # except ValidationError as e:
    #     logger.error(
    #         f"[UPDATE_METADATA_KEY] Validation error for current_name: {e.message}"
    #     )
    #     return UpdateMetadataKeyAction(
    #         name=new_name or "",
    #         title=UPDATE_METADATA_KEY_TITLE,
    #         confirmation_api_url=CONFIRMATION_API_URL,
    #         cancel_api_url=CANCEL_API_URL,
    #         error_message=(
    #             f"Invalid current metadata key name: {e.message}. "
    #             f"Details: {e.details if e.details else 'No additional details'}."
    #         ),
    #     )

    # Validate new_name
    try:
        validated_new_name = validate_string_field(
            new_name, "new_name", max_length=255, allow_empty=False
        )
    except ValidationError as e:
        logger.error(
            f"[UPDATE_METADATA_KEY] Validation error for new_name: {e.message}"
        )
        return MetadataActionError(
            is_error=True,
            error_code="INVALID_NEW_NAME",
            error_message=f"Invalid new metadata key name: {e.message}",
            details={"new_name": new_name, "validation_details": e.details},
        )

    # Check if a FREE key with the specified current_name exists
    logger.info(
        f"[UPDATE_METADATA_KEY] Checking for existing FREE metadata key with current_name '{current_name}'"
    )
    logger.debug("[UPDATE_METADATA_KEY] Calling get_free_metadata_keys API")
    try:
        keys_response = await conpass_api_service.get_free_metadata_keys()
        logger.info(
            f"[UPDATE_METADATA_KEY] FREE keys check response: "
            f"status={keys_response.status}, has_data={keys_response.data is not None}"
        )

        try:
            response_data = handle_api_response(
                keys_response,
                "checking for existing FREE metadata keys",
                context={
                    "current_name": current_name,
                    "new_name": validated_new_name,
                },
            )
        except (ApiError, NotFoundError) as e:
            # If we can't check for the key to update, we should fail
            logger.error(
                f"[UPDATE_METADATA_KEY] API error checking for metadata key: {e.message}"
            )
            return MetadataActionError(
                is_error=True,
                error_code="API_ERROR",
                error_message=f"Failed to check for existing metadata key: {e.message}. Cannot proceed with update.",
                details={
                    "current_name": current_name,
                    "new_name": validated_new_name,
                    "recoverable": getattr(e, "recoverable", False),
                },
            )

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
                f"Cannot verify if metadata key '{current_name}' exists."
            )
            logger.error(f"[UPDATE_METADATA_KEY] {error_msg}")
            return MetadataActionError(
                is_error=True,
                error_code="INVALID_RESPONSE_FORMAT",
                error_message=error_msg,
                details={
                    "current_name": current_name,
                    "new_name": validated_new_name,
                    "received_type": type(existing_keys).__name__,
                },
            )

        logger.debug(
            f"[UPDATE_METADATA_KEY] Checking {len(existing_keys)} existing FREE keys "
            f"for current key '{current_name}' and checking for duplicate with new name '{validated_new_name}'"
        )

        # Look for the key that needs to be updated and check for duplicate new name
        found_current_key = None
        duplicate_new_name_key = None

        for key in existing_keys:
            if not isinstance(key, dict):
                logger.warning(
                    f"[UPDATE_METADATA_KEY] Skipping invalid key: expected dict, got {type(key).__name__}"
                )
                continue

            key_name = key.get("name")

            # Check if this is the current key to update
            if key_name == current_name:
                found_current_key = key

            # Check if new name already exists (and it's not the same key)
            if key_name == validated_new_name and key_name != current_name:
                duplicate_new_name_key = key

        # Validate that the current key exists
        if not found_current_key:
            logger.warning(
                f"[UPDATE_METADATA_KEY] No FREE metadata key found with current name '{current_name}'"
            )
            return MetadataActionError(
                is_error=True,
                error_code="KEY_NOT_FOUND",
                error_message=f"No metadata key with name '{current_name}' exists. Please check the name and try again, or create a new key if needed.",
                details={"current_name": current_name, "new_name": validated_new_name},
            )

        # Check if the new name conflicts with another existing key
        if duplicate_new_name_key:
            duplicate_key_id = duplicate_new_name_key.get("id")
            logger.warning(
                f"[UPDATE_METADATA_KEY] Duplicate found: A FREE metadata key with name '{validated_new_name}' "
                f"already exists (id={duplicate_key_id})"
            )
            return MetadataActionError(
                is_error=True,
                error_code="DUPLICATE_KEY_NAME",
                error_message=f"Cannot update: A different metadata key with name '{validated_new_name}' already exists (ID: {duplicate_key_id}). Please use a different name.",
                details={
                    "current_name": current_name,
                    "new_name": validated_new_name,
                    "duplicate_key_id": duplicate_key_id,
                },
            )

        key_id = found_current_key.get("id")
        key_type = found_current_key.get("type", 2)
        is_visible = found_current_key.get("is_visible", True)
        key_status = found_current_key.get("status", 1)

        logger.info(
            f"[UPDATE_METADATA_KEY] Found FREE metadata key with current name '{current_name}' "
            f"(id={key_id}, type={key_type}, is_visible={is_visible}, status={key_status}). "
            f"New name '{validated_new_name}' is available."
        )

    except ValidationError as e:
        logger.error(f"[UPDATE_METADATA_KEY] Validation error: {e.message}")
        return MetadataActionError(
            is_error=True,
            error_code="VALIDATION_ERROR",
            error_message=f"Validation error: {e.message}",
            details={
                "current_name": current_name,
                "new_name": new_name,
                "validation_details": e.details,
            },
        )
    except (ApiError, NotFoundError) as e:
        logger.error(f"[UPDATE_METADATA_KEY] API error: {e.message}")
        return MetadataActionError(
            is_error=True,
            error_code="API_ERROR",
            error_message=f"Error checking for existing metadata key: {e.message}. Cannot proceed with update.",
            details={
                "current_name": current_name,
                "new_name": new_name,
                "recoverable": getattr(e, "recoverable", False),
            },
        )
    except Exception as e:
        error_msg = (
            f"Unexpected error checking for existing metadata key: {str(e)}. "
            f"Error type: {type(e).__name__}. "
            f"Cannot proceed with update."
        )
        logger.exception(f"[UPDATE_METADATA_KEY] {error_msg}")
        return MetadataActionError(
            is_error=True,
            error_code="UNEXPECTED_ERROR",
            error_message=error_msg,
            details={
                "current_name": current_name,
                "new_name": new_name,
                "error_type": type(e).__name__,
            },
        )

    # All validations passed - return action template
    logger.info(
        f"[UPDATE_METADATA_KEY] All validations passed. Creating action template for updating metadata key "
        f"from '{current_name}' to '{validated_new_name}' (key_id={key_id})"
    )

    hashed_metadata_action = generate_jwt_token(
        action = UpdateMetadataKeyAction(
            key_id=key_id,
            current_name=current_name,
            name=validated_new_name,
            title=UPDATE_METADATA_KEY_TITLE,
            confirmation_api_url=CONFIRMATION_API_URL,
            cancel_api_url=CANCEL_API_URL,
            status="pending",
            error_message=None,
        )
    )

    return UpdateMetadataKeyAction(
        key_id=key_id,
        current_name=current_name,
        name=validated_new_name,
        title=UPDATE_METADATA_KEY_TITLE,
        confirmation_api_url=CONFIRMATION_API_URL,
        cancel_api_url=CANCEL_API_URL,
        status="pending",
        error_message=None,
        jwt_token=hashed_metadata_action
    )
