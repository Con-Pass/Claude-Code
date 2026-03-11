from typing import List

from app.core.logging_config import get_logger
from app.services.conpass_api_service import ConpassApiService
from app.schemas.metadata_crud import (
    UpdateDirectoryMetadataVisibilityAction,
    DirectoryMetadataKeyUpdate,
    DirectoryMetadataKey,
    MetadataActionError,
)
from app.services.chatbot.tools.metadata_crud.error_handling import (
    ValidationError,
    ApiError,
    NotFoundError,
    validate_directory_id,
    validate_metadata_key_id,
    handle_api_response,
)
from app.utils.crud_metadata_hash_utils import generate_jwt_token

logger = get_logger(__name__)

# API URLs for directory metadata visibility update actions
CONFIRMATION_API_URL = "/metadata/update-directory-visibility"
CANCEL_API_URL = "/metadata/update-directory-visibility/cancel"

# Static title for update directory metadata visibility actions
UPDATE_DIRECTORY_METADATA_VISIBILITY_TITLE = "Update Directory Metadata Visibility"


async def generate_directory_metadata_visibility_update_action(
    conpass_api_service: ConpassApiService,
    directory_id: int,
    metadata_key_updates: List[DirectoryMetadataKey],
) -> UpdateDirectoryMetadataVisibilityAction | MetadataActionError:
    """
    Update visibility of metadata keys for a specific directory.

    This function validates inputs and returns an action template for user approval.
    After approval, the execution endpoint will:
    1. Fetch current directory metadata settings
    2. Merge updates with existing settings (preserve existing keys)
    3. Configure directory visibility via POST /setting/directory/meta/update

    Args:
        conpass_api_service: ConPass API service instance
        directory_id: Directory ID to update
        metadata_key_updates: List of dictionaries with:
            - key_id (int): MetaKey ID
            - key_type (str): "DEFAULT" or "FREE"
            - is_visible (bool): New visibility setting

    Returns:
        UpdateDirectoryMetadataVisibilityAction with validation results and action details
    """
    logger.info(
        f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Called with directory_id={directory_id}, "
        f"number_of_updates={len(metadata_key_updates) if metadata_key_updates else 0}"
    )

    # Validate directory_id
    try:
        validated_directory_id = validate_directory_id(directory_id)
    except ValidationError as e:
        logger.error(
            f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Validation error: {e.message}"
        )
        return MetadataActionError(
            is_error=True,
            error_code="INVALID_DIRECTORY_ID",
            error_message=f"Invalid directory_id: {e.message}",
            details={"directory_id": directory_id, "validation_details": e.details},
        )

    # Validate metadata_key_updates is not empty
    if metadata_key_updates is None:
        logger.error(
            "[UPDATE_DIRECTORY_METADATA_VISIBILITY] Validation failed: metadata_key_updates is None"
        )
        return MetadataActionError(
            is_error=True,
            error_code="MISSING_UPDATES",
            error_message="metadata_key_updates is required and cannot be None. Provide a list of metadata key updates.",
            details={"directory_id": validated_directory_id},
        )

    if not isinstance(metadata_key_updates, list):
        logger.error(
            f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Validation failed: metadata_key_updates must be a list, "
            f"got {type(metadata_key_updates).__name__}"
        )
        return MetadataActionError(
            is_error=True,
            error_code="INVALID_UPDATES_TYPE",
            error_message=f"metadata_key_updates must be a list, got {type(metadata_key_updates).__name__}. Provide a list of metadata key updates.",
            details={
                "directory_id": validated_directory_id,
                "received_type": type(metadata_key_updates).__name__,
            },
        )

    if len(metadata_key_updates) == 0:
        logger.error(
            "[UPDATE_DIRECTORY_METADATA_VISIBILITY] Validation failed: No metadata key updates provided"
        )
        return MetadataActionError(
            is_error=True,
            error_code="NO_UPDATES",
            error_message="At least one metadata key update is required. Each update must have key_id, key_type ('DEFAULT' or 'FREE'), and is_visible (boolean).",
            details={"directory_id": validated_directory_id},
        )

    # Validate directory exists and get directory name
    logger.info(
        f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Validating directory {validated_directory_id} exists"
    )
    logger.debug(
        f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Calling get_directory_metadata_settings API "
        f"with directory_id={validated_directory_id}"
    )
    directory_name = None
    dir_response_data = None  # Store for later use in key validation
    try:
        dir_response = await conpass_api_service.get_directory_metadata_settings(
            validated_directory_id
        )
        logger.info(
            f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Directory validation response: "
            f"status={dir_response.status}, has_data={dir_response.data is not None}"
        )

        try:
            dir_response_data = handle_api_response(
                dir_response,
                f"validating directory {validated_directory_id}",
                context={"directory_id": validated_directory_id},
            )
        except NotFoundError as e:
            logger.error(
                f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Not found error: {e.message}"
            )
            return MetadataActionError(
                is_error=True,
                error_code="DIRECTORY_NOT_FOUND",
                error_message=f"Directory {validated_directory_id} not found or you don't have access to it.",
                details={"directory_id": validated_directory_id, "error_details": e.message},
            )
        except ApiError as e:
            logger.error(
                f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] API error: {e.message}"
            )
            return MetadataActionError(
                is_error=True,
                error_code="API_ERROR",
                error_message=f"Failed to validate directory {validated_directory_id}: {e.message}",
                details={
                    "directory_id": validated_directory_id,
                    "recoverable": e.recoverable,
                },
            )

        # Try to extract directory name for display (optional, may not be in response)
        if isinstance(dir_response_data, dict):
            directory_name = dir_response_data.get("directory_name")
            if directory_name:
                logger.debug(
                    f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Extracted directory name: '{directory_name}'"
                )

        logger.info(
            f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Directory {validated_directory_id} validated successfully"
        )
    except ValidationError as e:
        logger.error(
            f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Validation error: {e.message}"
        )
        return MetadataActionError(
            is_error=True,
            error_code="VALIDATION_ERROR",
            error_message=f"Validation error: {e.message}",
            details={"directory_id": validated_directory_id, "validation_details": e.details},
        )
    except (ApiError, NotFoundError) as e:
        logger.error(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] API error: {e.message}")
        return MetadataActionError(
            is_error=True,
            error_code="API_ERROR",
            error_message=f"Error validating directory: {e.message}",
            details={
                "directory_id": validated_directory_id,
                "recoverable": getattr(e, "recoverable", False),
            },
        )
    except Exception as e:
        error_msg = (
            f"Unexpected error validating directory {validated_directory_id}: {str(e)}. "
            f"Error type: {type(e).__name__}."
        )
        logger.exception(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
        return MetadataActionError(
            is_error=True,
            error_code="UNEXPECTED_ERROR",
            error_message=error_msg,
            details={
                "directory_id": validated_directory_id,
                "error_type": type(e).__name__,
            },
        )

    # Validate all metadata keys exist and are accessible
    logger.info(
        f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Validating {len(metadata_key_updates)} metadata key(s)"
    )
    logger.debug(
        "[UPDATE_DIRECTORY_METADATA_VISIBILITY] Calling get_all_metadata_keys API"
    )
    try:
        keys_response = await conpass_api_service.get_all_metadata_keys()
        logger.info(
            f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Metadata keys check response: "
            f"status={keys_response.status}, has_data={keys_response.data is not None}"
        )

        try:
            keys_response_data = handle_api_response(
                keys_response,
                "fetching all metadata keys for validation",
                context={"directory_id": validated_directory_id},
            )
        except (ApiError, NotFoundError) as e:
            logger.error(
                f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] API error: {e.message}"
            )
            return MetadataActionError(
                is_error=True,
                error_code="API_ERROR",
                error_message=f"Failed to fetch metadata keys for validation: {e.message}",
                details={
                    "directory_id": validated_directory_id,
                    "directory_name": directory_name,
                    "recoverable": getattr(e, "recoverable", False),
                },
            )

        # Extract available keys - handle both direct list and wrapped in "response" key
        available_keys = []
        if isinstance(keys_response_data, list):
            available_keys = keys_response_data
        elif isinstance(keys_response_data, dict):
            # Check if wrapped in "response" key (like read_metadata does)
            if "response" in keys_response_data:
                response_list = keys_response_data.get("response", [])
                if isinstance(response_list, list):
                    available_keys = response_list
            else:
                # Try direct access
                available_keys = keys_response_data.get("data", [])

        if not isinstance(available_keys, list):
            error_msg = (
                f"Invalid response format from API: expected list of keys, got {type(available_keys).__name__}. "
                f"Cannot validate metadata keys for directory {validated_directory_id}."
            )
            logger.error(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
            return MetadataActionError(
                is_error=True,
                error_code="INVALID_RESPONSE_FORMAT",
                error_message=error_msg,
                details={
                    "directory_id": validated_directory_id,
                    "directory_name": directory_name,
                    "received_type": type(available_keys).__name__,
                },
            )

        # Build a map of available keys by ID and type from account-level
        account_key_map = {}
        for key in available_keys:
            if isinstance(key, dict):
                key_id = key.get("id")
                key_type = key.get("type")
                if key_id is not None and key_type is not None:
                    # Map by (id, type) to handle cases where DEFAULT and FREE might have same ID (unlikely but safe)
                    # type is an integer: 1 for DEFAULT, 2 for FREE
                    account_key_map[(key_id, key_type)] = key

        # Also build a map from directory metadata settings (keys already configured for this directory)
        directory_key_map = {}
        if isinstance(dir_response_data, dict) and "response" in dir_response_data:
            dir_response_dict = dir_response_data.get("response", {})
            if not isinstance(dir_response_dict, dict):
                logger.warning(
                    f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Invalid directory response format: "
                    f"expected dict, got {type(dir_response_dict).__name__}"
                )
            else:
                default_list = dir_response_dict.get("default_list", [])
                free_list = dir_response_dict.get("free_list", [])

                if not isinstance(default_list, list):
                    default_list = []
                if not isinstance(free_list, list):
                    free_list = []

                for key in default_list + free_list:
                    if isinstance(key, dict):
                        key_id = key.get("id")
                        key_type = key.get("type")
                        if key_id is not None and key_type is not None:
                            directory_key_map[(key_id, key_type)] = key

        logger.debug(
            f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Found {len(account_key_map)} account-level metadata keys "
            f"and {len(directory_key_map)} directory-configured keys"
        )

        # Log some key IDs for debugging
        if account_key_map:
            sample_keys = list(account_key_map.keys())[:5]
            logger.debug(
                f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Sample account keys: {sample_keys}"
            )
        if directory_key_map:
            sample_dir_keys = list(directory_key_map.keys())[:5]
            logger.debug(
                f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Sample directory keys: {sample_dir_keys}"
            )

        # Validate each update
        validated_updates: list[DirectoryMetadataKeyUpdate] = []
        validation_errors = []
        for idx, update in enumerate(metadata_key_updates, 1):
            if not isinstance(update, dict):
                error_msg = (
                    f"Update {idx}: Invalid format, expected dict, got {type(update).__name__}. "
                    f"Each update must be a dictionary with key_id, key_type, and is_visible fields."
                )
                logger.warning(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
                validation_errors.append(error_msg)
                continue

            key_id = update.get("key_id")
            key_type_str = update.get("key_type")
            is_visible = update.get("is_visible")

            # Validate required fields
            if key_id is None:
                error_msg = (
                    f"Update {idx}: Missing required field 'key_id'. "
                    f"Each update must have key_id (integer), key_type ('DEFAULT' or 'FREE'), and is_visible (boolean)."
                )
                logger.warning(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
                validation_errors.append(error_msg)
                continue

            try:
                validated_key_id = validate_metadata_key_id(
                    key_id, f"key_id (update {idx})"
                )
            except ValidationError as e:
                error_msg = f"Update {idx}: Invalid key_id: {e.message}"
                logger.warning(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
                validation_errors.append(error_msg)
                continue

            if key_type_str not in ["DEFAULT", "FREE"]:
                error_msg = (
                    f"Update {idx}: Invalid key_type '{key_type_str}', must be 'DEFAULT' or 'FREE'. "
                    f"Got: {key_type_str}"
                )
                logger.warning(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
                validation_errors.append(error_msg)
                continue

            if is_visible is None:
                error_msg = (
                    f"Update {idx}: Missing required field 'is_visible'. "
                    f"Each update must have is_visible (boolean) to set visibility."
                )
                logger.warning(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
                validation_errors.append(error_msg)
                continue

            if not isinstance(is_visible, bool):
                error_msg = (
                    f"Update {idx}: Invalid is_visible value, must be boolean (True or False), "
                    f"got {type(is_visible).__name__}: {is_visible}"
                )
                logger.warning(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
                validation_errors.append(error_msg)
                continue

            # Convert key_type string to integer for lookup
            key_type_int = 1 if key_type_str == "DEFAULT" else 2

            # Check if key exists - first check directory settings, then account-level
            key_info = directory_key_map.get((validated_key_id, key_type_int))
            if not key_info:
                key_info = account_key_map.get((validated_key_id, key_type_int))

            if not key_info:
                # Try to find the key by ID only (in case type mismatch)
                found_by_id = None
                # Check both maps
                for key_map_to_check in [directory_key_map, account_key_map]:
                    for (k_id, k_type), k_info in key_map_to_check.items():
                        if k_id == validated_key_id:
                            found_by_id = (k_id, k_type, k_info)
                            break
                    if found_by_id:
                        break

                if found_by_id:
                    actual_type = "DEFAULT" if found_by_id[1] == 1 else "FREE"
                    error_msg = (
                        f"Update {idx}: Metadata key {validated_key_id} exists but type mismatch. "
                        f"Expected {key_type_str} (type {key_type_int}), but found {actual_type} (type {found_by_id[1]}). "
                        f"Please use the correct key_type for this metadata key."
                    )
                    logger.warning(
                        f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}"
                    )
                    return MetadataActionError(
                        is_error=True,
                        error_code="KEY_TYPE_MISMATCH",
                        error_message=error_msg,
                        details={
                            "directory_id": validated_directory_id,
                            "directory_name": directory_name,
                            "key_id": validated_key_id,
                            "expected_type": key_type_str,
                            "actual_type": actual_type,
                        },
                    )

                # Key not found at all
                all_key_ids = sorted(
                    set(
                        k[0]
                        for k in list(account_key_map.keys())
                        + list(directory_key_map.keys())
                    )
                )
                available_ids_str = ", ".join(str(id) for id in all_key_ids[:20])
                if len(all_key_ids) > 20:
                    available_ids_str += f" (and {len(all_key_ids) - 20} more)"
                error_msg = (
                    f"Update {idx}: Metadata key {validated_key_id} (type {key_type_str}) not found or not accessible. "
                    f"Available key IDs: {available_ids_str if all_key_ids else 'none'}. "
                    f"Use read_metadata tool to see all available metadata keys."
                )
                logger.warning(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
                return MetadataActionError(
                    is_error=True,
                    error_code="KEY_NOT_FOUND",
                    error_message=error_msg,
                    details={
                        "directory_id": validated_directory_id,
                        "directory_name": directory_name,
                        "key_id": validated_key_id,
                        "key_type": key_type_str,
                        "available_key_ids": all_key_ids[:20],
                    },
                )

            # Check if key is in ENABLE status
            key_status = key_info.get("status")
            if key_status != 1:  # 1 = ENABLE
                error_msg = (
                    f"Update {idx}: Metadata key {validated_key_id} (type {key_type_str}, name: '{key_info.get('name', 'N/A')}') "
                    f"is not in ENABLE status (current status: {key_status}). "
                    f"Only enabled metadata keys can be configured for directory visibility."
                )
                logger.warning(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
                return MetadataActionError(
                    is_error=True,
                    error_code="KEY_NOT_ENABLED",
                    error_message=error_msg,
                    details={
                        "directory_id": validated_directory_id,
                        "directory_name": directory_name,
                        "key_id": validated_key_id,
                        "key_type": key_type_str,
                        "key_name": key_info.get("name"),
                        "key_status": key_status,
                    },
                )

            # Get current directory settings to find meta_key_directory_id if it exists
            meta_key_directory_id = None
            if isinstance(dir_response_data, dict) and "response" in dir_response_data:
                dir_response_dict = dir_response_data.get("response", {})
                if isinstance(dir_response_dict, dict):
                    default_list = dir_response_dict.get("default_list", [])
                    free_list = dir_response_dict.get("free_list", [])

                    if not isinstance(default_list, list):
                        default_list = []
                    if not isinstance(free_list, list):
                        free_list = []

                    # Search for existing association
                    search_list = (
                        default_list if key_type_str == "DEFAULT" else free_list
                    )
                    for existing_key in search_list:
                        if (
                            isinstance(existing_key, dict)
                            and existing_key.get("id") == validated_key_id
                        ):
                            meta_key_directory_id = existing_key.get(
                                "meta_key_directory_id"
                            )
                            break

            # Create validated update
            validated_update = DirectoryMetadataKeyUpdate(
                key_id=validated_key_id,
                key_name=key_info.get("name"),
                key_type=key_type_str,
                is_visible=bool(is_visible),
                meta_key_directory_id=meta_key_directory_id,
            )
            validated_updates.append(validated_update)
            logger.debug(
                f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Update {idx}: Validated key_id={validated_key_id}, "
                f"key_name='{key_info.get('name')}', key_type={key_type_str}, is_visible={is_visible}, "
                f"meta_key_directory_id={meta_key_directory_id}"
            )

        if validation_errors:
            error_msg = f"Validation failed for {len(validation_errors)} update(s) out of {len(metadata_key_updates)}"
            logger.error(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
            return MetadataActionError(
                is_error=True,
                error_code="VALIDATION_FAILED",
                error_message=error_msg,
                details={
                    "directory_id": validated_directory_id,
                    "directory_name": directory_name,
                    "validation_errors": validation_errors,
                },
            )

        if not validated_updates:
            error_msg = (
                "No valid metadata key updates found after validation. "
                "Please check that all key_ids exist, are accessible, and are in ENABLE status. "
                "Each update must have: key_id (integer), key_type ('DEFAULT' or 'FREE'), and is_visible (boolean)."
            )
            logger.error(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
            return MetadataActionError(
                is_error=True,
                error_code="NO_VALID_UPDATES",
                error_message=error_msg,
                details={
                    "directory_id": validated_directory_id,
                    "directory_name": directory_name,
                },
            )

        logger.info(
            f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Validated {len(validated_updates)} metadata key update(s) "
            f"for directory {validated_directory_id}"
        )

    except ValidationError as e:
        logger.error(
            f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] Validation error: {e.message}"
        )
        return MetadataActionError(
            is_error=True,
            error_code="VALIDATION_ERROR",
            error_message=f"Validation error: {e.message}",
            details={
                "directory_id": validated_directory_id,
                "directory_name": directory_name,
                "validation_details": e.details,
            },
        )
    except (ApiError, NotFoundError) as e:
        logger.error(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] API error: {e.message}")
        return MetadataActionError(
            is_error=True,
            error_code="API_ERROR",
            error_message=f"Error validating metadata keys: {e.message}",
            details={
                "directory_id": validated_directory_id,
                "directory_name": directory_name,
                "recoverable": getattr(e, "recoverable", False),
            },
        )
    except Exception as e:
        error_msg = (
            f"Unexpected error validating metadata keys: {str(e)}. "
            f"Error type: {type(e).__name__}."
        )
        logger.exception(f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] {error_msg}")
        return MetadataActionError(
            is_error=True,
            error_code="UNEXPECTED_ERROR",
            error_message=error_msg,
            details={
                "directory_id": validated_directory_id,
                "directory_name": directory_name,
                "error_type": type(e).__name__,
            },
        )

    # All validations passed - return action template
    logger.info(
        f"[UPDATE_DIRECTORY_METADATA_VISIBILITY] All validations passed. Creating action template "
        f"for {len(validated_updates)} metadata key update(s) in directory {validated_directory_id} "
        f"(directory_name={directory_name})"
    )

    hashed_metadata_action = generate_jwt_token(
        action=UpdateDirectoryMetadataVisibilityAction(
            directory_id=validated_directory_id,
            directory_name=directory_name,
            metadata_key_updates=validated_updates,
            title=UPDATE_DIRECTORY_METADATA_VISIBILITY_TITLE,
            confirmation_api_url=CONFIRMATION_API_URL,
            cancel_api_url=CANCEL_API_URL,
            status="pending",
            error_message=None,
        )
    )

    return UpdateDirectoryMetadataVisibilityAction(
        directory_id=validated_directory_id,
        directory_name=directory_name,
        metadata_key_updates=validated_updates,
        title=UPDATE_DIRECTORY_METADATA_VISIBILITY_TITLE,
        confirmation_api_url=CONFIRMATION_API_URL,
        cancel_api_url=CANCEL_API_URL,
        status="pending",
        error_message=None,
        jwt_token=hashed_metadata_action
    )
