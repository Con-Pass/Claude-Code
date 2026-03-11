import re
from typing import List

from app.core.logging_config import get_logger
from app.services.conpass_api_service import ConpassApiService
from app.schemas.metadata_crud import (
    UpdateMetadataAction,
    MetadataItem,
    # MetadataUpdateItem,
    MetadataUpdateItemV2,
    MetadataActionError,
)
from app.services.chatbot.tools.metadata_crud.error_handling import (
    ValidationError,
    ApiError,
    NotFoundError,
    validate_contract_id,
    handle_api_response,
)
from app.utils.crud_metadata_hash_utils import generate_jwt_token

logger = get_logger(__name__)

# API URLs for metadata update actions
CONFIRMATION_API_URL = "/metadata/update"
CANCEL_API_URL = "/metadata/update/cancel"

# Static title for update metadata actions
UPDATE_METADATA_TITLE = "Update Metadata"

# Valid contract type values (must match exactly in Japanese)
VALID_CONTRACT_TYPES = [
    "秘密保持契約書",
    "雇用契約書",
    "申込注文書",
    "業務委託契約書",
    "売買契約書",
    "請負契約書",
    "賃貸借契約書",
    "派遣契約書",
    "金銭消費貸借契約",
    "代理店契約書",
    "業務提携契約書",
    "ライセンス契約書",
    "顧問契約書",
    "譲渡契約書",
    "和解契約書",
    "誓約書",
    "その他",
]

# Fixed metadata field type mapping
# Maps key_id to (field_type, label, name_japanese)
# Field types: TEXT, DATE, PERSON, CONTRACT_TYPE
FIXED_METADATA_MAP = {
    1: ("TEXT", "title", "契約書名"),
    2: ("TEXT", "companya", "会社名（甲）"),
    3: ("TEXT", "companyb", "会社名（乙）"),
    4: ("TEXT", "companyc", "会社名（丙）"),
    5: ("TEXT", "companyd", "会社名（丁）"),
    6: ("DATE", "contractdate", "契約日"),
    7: ("DATE", "contractstartdate", "契約開始日"),
    8: ("DATE", "contractenddate", "契約終了日"),
    9: ("TEXT", "autoupdate", "自動更新の有無"),
    10: ("DATE", "cancelnotice", "解約ノーティス日"),
    11: ("TEXT", "docid", "管理番号"),
    12: ("TEXT", "related_contract", "関連契約書"),
    13: ("DATE", "related_contract_date", "関連契約日"),
    14: ("TEXT", "cort", "裁判所"),
    15: ("TEXT", "outsource", "再委託禁止"),
    16: ("CONTRACT_TYPE", "conpass_contract_type", "契約種別"),
    17: ("PERSON", "conpass_person", "担当者名"),
    18: ("TEXT", "conpass_contract_renew_notify", "契約更新通知"),
    19: ("TEXT", "conpass_amount", "金額"),
    20: ("TEXT", "antisocial", "反社条項の有無"),
}

# Date field key IDs for quick lookup
DATE_FIELD_IDS = {6, 7, 8, 10, 13}

# Contract type field key ID
CONTRACT_TYPE_KEY_ID = 16

# Person field key ID
PERSON_KEY_ID = 17


def _get_metadata_field_type(key_id: int, key_label: str) -> str:
    """
    Get the field type for a fixed metadata field.

    Args:
        key_id: MetaKey ID (1-20 for fixed metadata)
        key_label: MetaKey label (e.g., "title", "conpass_person")

    Returns:
        Field type: "TEXT", "DATE", "PERSON", "CONTRACT_TYPE", or "UNKNOWN"
    """
    if key_id in FIXED_METADATA_MAP:
        return FIXED_METADATA_MAP[key_id][0]

    # Fallback to label-based detection if key_id not in map
    if key_label == "conpass_person":
        return "PERSON"
    elif key_label == "conpass_contract_type":
        return "CONTRACT_TYPE"
    elif key_label in (
        "contractdate",
        "contractstartdate",
        "contractenddate",
        "cancelnotice",
        "related_contract_date",
    ):
        return "DATE"

    return "UNKNOWN"


def _is_date_field(key_id: int, key_label: str) -> bool:
    """Check if a field is a date type."""
    return (
        key_id in DATE_FIELD_IDS
        or _get_metadata_field_type(key_id, key_label) == "DATE"
    )


def _is_contract_type_field(key_id: int, key_label: str) -> bool:
    """Check if a field is contract type."""
    return key_id == CONTRACT_TYPE_KEY_ID or key_label == "conpass_contract_type"


def _is_person_field(key_id: int, key_label: str) -> bool:
    """Check if a field is person type."""
    return key_id == PERSON_KEY_ID or key_label == "conpass_person"


def _validate_contract_type_value(value: str) -> tuple[bool, str]:
    """
    Validate contract type value against predefined options.

    Args:
        value: The contract type value to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if value is valid, False otherwise
        - error_message: Error message if invalid, empty string if valid
    """
    if value not in VALID_CONTRACT_TYPES:
        valid_options_str = ", ".join(f'"{opt}"' for opt in VALID_CONTRACT_TYPES)
        return False, (
            f"Invalid contract type value: '{value}'. "
            f"Must be one of: {valid_options_str}"
        )
    return True, ""


def _validate_date_format(date_str: str) -> bool:
    """Validate date format is YYYY-MM-DD."""
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    if not re.match(pattern, date_str):
        return False
    # Additional validation: check if it's a valid date
    try:
        from datetime import datetime

        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


async def _get_valid_user_ids(
    conpass_api_service: ConpassApiService,
) -> set[int]:
    """
    Fetch valid user IDs from the API.

    Args:
        conpass_api_service: The API service instance

    Returns:
        Set of valid user IDs
    """
    try:
        response = await conpass_api_service.get_user_list()
        if response.status == "success" and response.data:
            # Handle both direct list and wrapped response formats
            user_list = []
            if isinstance(response.data, list):
                user_list = response.data
            elif isinstance(response.data, dict):
                # Check for common wrapper keys
                if "response" in response.data:
                    user_list = response.data.get("response", [])
                elif "data" in response.data:
                    user_list = response.data.get("data", [])
                elif "users" in response.data:
                    user_list = response.data.get("users", [])
                else:
                    logger.warning(
                        f"[UPDATE_METADATA] Unexpected response format: {type(response.data)}, "
                        f"keys: {list(response.data.keys()) if isinstance(response.data, dict) else 'N/A'}"
                    )
                    # Log the actual response structure for debugging
                    logger.debug(
                        f"[UPDATE_METADATA] Full response.data structure: {response.data}"
                    )

            if not isinstance(user_list, list):
                logger.warning(
                    f"[UPDATE_METADATA] Expected list but got {type(user_list)}: {user_list}"
                )
                user_list = []

            valid_user_ids = set()
            for user in user_list:
                if isinstance(user, dict) and "id" in user:
                    user_id = user.get("id")
                    if user_id is not None:
                        try:
                            valid_user_ids.add(int(user_id))
                        except (ValueError, TypeError):
                            logger.warning(
                                f"Invalid user ID in user list: {user_id} (type: {type(user_id)})"
                            )
            logger.info(
                f"[UPDATE_METADATA] Fetched {len(valid_user_ids)} valid user IDs from API "
                f"(from {len(user_list)} total users)"
            )
            return valid_user_ids
        else:
            logger.warning(
                f"[UPDATE_METADATA] Failed to fetch user list: status={response.status}, "
                f"has_data={response.data is not None}"
            )
            if response.data is not None:
                logger.debug(
                    f"[UPDATE_METADATA] Response data type: {type(response.data)}, "
                    f"value: {response.data}"
                )
            return set()
    except Exception as e:
        logger.exception(f"[UPDATE_METADATA] Exception while fetching user list: {e}")
        return set()


async def _get_user_list_with_names(
    conpass_api_service: ConpassApiService,
) -> dict[str, int]:
    """
    Fetch user list and create a mapping of names/usernames to user IDs.

    Args:
        conpass_api_service: The API service instance

    Returns:
        Dictionary mapping names/usernames (lowercase) to user IDs
        Format: {"john doe": 1, "jane smith": 2, "refadul": 3, ...}
    """
    try:
        response = await conpass_api_service.get_user_list()
        if response.status == "success" and response.data:
            # Handle both direct list and wrapped response formats
            user_list = []
            if isinstance(response.data, list):
                user_list = response.data
            elif isinstance(response.data, dict):
                # Check for common wrapper keys
                if "response" in response.data:
                    user_list = response.data.get("response", [])
                elif "data" in response.data:
                    user_list = response.data.get("data", [])
                elif "users" in response.data:
                    user_list = response.data.get("users", [])
                else:
                    logger.warning(
                        f"[UPDATE_METADATA] Unexpected response format for name mapping: {type(response.data)}, "
                        f"keys: {list(response.data.keys()) if isinstance(response.data, dict) else 'N/A'}"
                    )
                    # Log the actual response structure for debugging
                    logger.debug(
                        f"[UPDATE_METADATA] Full response.data structure for name mapping: {response.data}"
                    )

            if not isinstance(user_list, list):
                logger.warning(
                    f"[UPDATE_METADATA] Expected list but got {type(user_list)} for name mapping: {user_list}"
                )
                user_list = []

            name_to_id_map = {}
            for user in user_list:
                if isinstance(user, dict) and "id" in user:
                    user_id = user.get("id")
                    if user_id is not None:
                        try:
                            user_id_int = int(user_id)
                            # Map userName (camelCase field name from API)
                            user_name = user.get("userName", "").strip()
                            if user_name:
                                name_to_id_map[user_name.lower()] = user_id_int
                            # Map email field
                            email = user.get("email", "").strip()
                            if email:
                                name_to_id_map[email.lower()] = user_id_int
                                # Also use part before @ if it's an email
                                if "@" in email:
                                    email_prefix = email.split("@")[0].lower()
                                    if email_prefix:
                                        name_to_id_map[email_prefix] = user_id_int
                        except (ValueError, TypeError):
                            logger.warning(
                                f"Invalid user ID in user list: {user_id} (type: {type(user_id)})"
                            )
            logger.info(
                f"[UPDATE_METADATA] Built name-to-ID mapping with {len(name_to_id_map)} entries "
                f"(from {len(user_list)} total users)"
            )
            return name_to_id_map
        else:
            logger.warning(
                f"[UPDATE_METADATA] Failed to fetch user list for name mapping: status={response.status}, "
                f"has_data={response.data is not None}"
            )
            if response.data is not None:
                logger.debug(
                    f"[UPDATE_METADATA] Response data type for name mapping: {type(response.data)}, "
                    f"value: {response.data}"
                )
            return {}
    except Exception as e:
        logger.exception(
            f"[UPDATE_METADATA] Exception while fetching user list for name mapping: {e}"
        )
        return {}


async def _search_user_by_name(
    conpass_api_service: ConpassApiService,
    name: str,
    name_to_id_map: dict[str, int],
) -> int | None:
    """
    Search for a user by name using fuzzy matching.

    Args:
        conpass_api_service: The API service instance
        name: The name to search for
        name_to_id_map: Pre-built mapping of names to IDs

    Returns:
        User ID if found, None otherwise
    """
    name_lower = name.strip().lower()
    if not name_lower:
        return None

    # First, try exact match in the pre-built map
    if name_lower in name_to_id_map:
        logger.debug(
            f"[UPDATE_METADATA] Found exact match for '{name}': user_id={name_to_id_map[name_lower]}"
        )
        return name_to_id_map[name_lower]

    # Try fuzzy matching - check if name is contained in any key
    # (e.g., "refadul" matches "refadul@example.com" or "Refadul User")
    # Also handle spaces: "social test" should match "socialtest0622"
    name_no_spaces = name_lower.replace(" ", "").replace("-", "").replace("_", "")
    for mapped_name, user_id in name_to_id_map.items():
        mapped_no_spaces = (
            mapped_name.replace(" ", "").replace("-", "").replace("_", "")
        )

        # Check various matching strategies
        if (
            name_lower in mapped_name
            or mapped_name in name_lower
            or name_no_spaces in mapped_name
            or mapped_name in name_no_spaces
            or name_no_spaces in mapped_no_spaces
            or mapped_no_spaces in name_no_spaces
        ):
            logger.debug(
                f"[UPDATE_METADATA] Found fuzzy match for '{name}': '{mapped_name}' -> user_id={user_id}"
            )
            return user_id

    # If no match in pre-built map, try API search with userName filter
    try:
        response = await conpass_api_service.get_user_list()
        if response.status == "success" and response.data:
            # Handle both direct list and wrapped response formats
            user_list = []
            if isinstance(response.data, list):
                user_list = response.data
            elif isinstance(response.data, dict):
                # Check for common wrapper keys
                if "response" in response.data:
                    user_list = response.data.get("response", [])
                elif "data" in response.data:
                    user_list = response.data.get("data", [])
                elif "users" in response.data:
                    user_list = response.data.get("users", [])

            if not isinstance(user_list, list):
                user_list = []

            # Find best match
            name_no_spaces = (
                name_lower.replace(" ", "").replace("-", "").replace("_", "")
            )
            for user in user_list:
                if isinstance(user, dict) and "id" in user:
                    user_id = user.get("id")
                    if user_id is not None:
                        user_name = user.get("userName", "").strip().lower()
                        email = user.get("email", "").strip().lower()
                        user_name_no_spaces = (
                            user_name.replace(" ", "").replace("-", "").replace("_", "")
                        )
                        email_no_spaces = (
                            email.replace(" ", "").replace("-", "").replace("_", "")
                        )

                        # Check if name matches userName or email (with space handling)
                        if (
                            name_lower in user_name
                            or user_name in name_lower
                            or name_lower in email
                            or email in name_lower
                            or name_no_spaces in user_name
                            or user_name in name_no_spaces
                            or name_no_spaces in user_name_no_spaces
                            or user_name_no_spaces in name_no_spaces
                            or name_no_spaces in email
                            or email in name_no_spaces
                            or name_no_spaces in email_no_spaces
                            or email_no_spaces in name_no_spaces
                        ):
                            try:
                                logger.debug(
                                    f"[UPDATE_METADATA] Found API match for '{name}': user_id={user_id}"
                                )
                                return int(user_id)
                            except (ValueError, TypeError):
                                continue
    except Exception as e:
        logger.warning(
            f"[UPDATE_METADATA] Exception while searching for user '{name}': {e}"
        )

    logger.warning(f"[UPDATE_METADATA] No user found matching name '{name}'")
    return None


async def _resolve_person_names_to_ids(
    conpass_api_service: ConpassApiService,
    person_input: str,
    name_to_id_map: dict[str, int],
) -> tuple[list[int], list[str]]:
    """
    Resolve comma-separated person names/IDs to a list of person IDs.

    Args:
        conpass_api_service: The API service instance
        person_input: Comma-separated person names or IDs (e.g., "1,2,3" or "John Doe, Jane Smith")
        name_to_id_map: Pre-built mapping of names to IDs

    Returns:
        Tuple of (resolved_person_ids, unresolved_names)
        - resolved_person_ids: List of successfully resolved person IDs
        - unresolved_names: List of names that couldn't be resolved
    """
    if not person_input or not person_input.strip():
        return [], []

    person_items = [item.strip() for item in person_input.split(",") if item.strip()]
    resolved_ids = []
    unresolved_names = []

    for item in person_items:
        # Check if it's already a numeric ID
        if item.isdigit():
            try:
                resolved_ids.append(int(item))
                logger.debug(
                    f"[UPDATE_METADATA] Person item '{item}' is numeric ID: {int(item)}"
                )
            except ValueError:
                unresolved_names.append(item)
        else:
            # It's a name - try to resolve it
            user_id = await _search_user_by_name(
                conpass_api_service, item, name_to_id_map
            )
            if user_id is not None:
                resolved_ids.append(user_id)
                logger.info(
                    f"[UPDATE_METADATA] Resolved person name '{item}' to user_id={user_id}"
                )
            else:
                unresolved_names.append(item)
                logger.warning(
                    f"[UPDATE_METADATA] Could not resolve person name '{item}' to a user ID"
                )

    return resolved_ids, unresolved_names


async def generate_contract_metadata_update_action(
    conpass_api_service: ConpassApiService,
    contract_id: int,
    updates: List[MetadataUpdateItemV2],
) -> UpdateMetadataAction | MetadataActionError:
    logger.info(
        f"[UPDATE_METADATA] Called with contract_id={contract_id}, "
        f"number_of_updates={len(updates) if updates else 0}"
    )
    logger.debug(
        f"[UPDATE_METADATA] Update details for contract_id={contract_id}: {updates}"
    )

    # Validate contract_id
    try:
        validated_contract_id = validate_contract_id(contract_id)
    except ValidationError as e:
        logger.error(f"[UPDATE_METADATA] Validation error: {e.message}")
        return MetadataActionError(
            is_error=True,
            error_code="INVALID_CONTRACT_ID",
            error_message=f"Invalid contract_id: {e.message}",
            details={"contract_id": contract_id, "validation_details": e.details},
        )

    # Validate updates list
    if updates is None:
        logger.error("[UPDATE_METADATA] Updates list is None")
        return MetadataActionError(
            is_error=True,
            error_code="MISSING_UPDATES",
            error_message="Updates list is required and cannot be None. Provide a list of metadata update items.",
            details={"contract_id": validated_contract_id},
        )

    if not isinstance(updates, list):
        logger.error(
            f"[UPDATE_METADATA] Updates must be a list, got: {type(updates).__name__}"
        )
        return MetadataActionError(
            is_error=True,
            error_code="INVALID_UPDATES_TYPE",
            error_message=f"Updates must be a list, got: {type(updates).__name__}. Provide a list of metadata update items.",
            details={"contract_id": validated_contract_id, "received_type": type(updates).__name__},
        )

    # Convert dictionaries to MetadataUpdateItem instances if needed
    # (LLM tools may pass dicts instead of Pydantic models)
    logger.debug(
        f"[UPDATE_METADATA] Validating and converting {len(updates)} update item(s)"
    )
    validated_updates = []
    validation_errors: List[str] = []
    for idx, update in enumerate(updates, 1):
        if isinstance(update, dict):
            logger.debug(
                f"[UPDATE_METADATA] Converting update {idx}/{len(updates)} from dict to MetadataUpdateItem: {update}"
            )
            try:
                validated_update = MetadataUpdateItemV2(**update)
                validated_updates.append(validated_update)
                logger.debug(
                    f"[UPDATE_METADATA] Successfully converted update {idx} to MetadataUpdateItem"
                )
            except Exception as e:
                error_msg = (
                    f"Invalid update item {idx}: {str(e)}. "
                    f"Required fields: either metadata_id (for updates) or key_id (for creates). "
                    f"Optional fields: value, date_value, lock. "
                    f"Update data: {update}"
                )
                logger.error(f"[UPDATE_METADATA] {error_msg}")
                validation_errors.append(error_msg)
        elif isinstance(update, MetadataUpdateItemV2):
            logger.debug(
                f"[UPDATE_METADATA] Update {idx} is already a MetadataUpdateItem instance"
            )
            validated_updates.append(update)
        else:
            error_msg = (
                f"Update item {idx} has invalid type: {type(update).__name__}. "
                f"Must be a dict or MetadataUpdateItem. "
                f"Value: {update}"
            )
            logger.error(f"[UPDATE_METADATA] {error_msg}")
            validation_errors.append(error_msg)

    if validation_errors:
        return MetadataActionError(
            is_error=True,
            error_code="VALIDATION_FAILED",
            error_message=f"Validation failed for {len(validation_errors)} update item(s)",
            details={
                "contract_id": validated_contract_id,
                "validation_errors": validation_errors,
            },
        )

    logger.info(
        f"[UPDATE_METADATA] Validated {len(validated_updates)} update item(s) from {len(updates) if updates else 0} input(s)"
    )

    metadata_items = []
    errors: List[str] = []

    # Validate input
    if not validated_updates:
        logger.warning(
            f"[UPDATE_METADATA] No valid updates provided for contract_id={validated_contract_id}"
        )
        return MetadataActionError(
            is_error=True,
            error_code="NO_VALID_UPDATES",
            error_message="At least one valid update item is required. Each update item must have either metadata_id (for updates) or key_id (for creates).",
            details={"contract_id": validated_contract_id},
        )

    # Fetch current metadata once for efficiency
    logger.info(
        f"[UPDATE_METADATA] Fetching current metadata for contract_id={validated_contract_id}"
    )
    logger.debug(
        f"[UPDATE_METADATA] Calling get_contract_metadata API for contract_id={validated_contract_id}"
    )
    current_metadata_map = {}  # Map by metadata_id (for existing records)
    key_metadata_map = {}  # Map by key_id (for all records, including null id)
    try:
        full_response = await conpass_api_service.get_contract_metadata(
            validated_contract_id
        )
        logger.info(
            f"[UPDATE_METADATA] Metadata fetch response: status={full_response.status}, "
            f"has_data={full_response.data is not None}"
        )

        try:
            response_data = handle_api_response(
                full_response,
                f"fetching metadata for contract {validated_contract_id}",
                context={"contract_id": validated_contract_id},
            )
        except NotFoundError as e:
            logger.error(f"[UPDATE_METADATA] Not found error: {e.message}")
            return MetadataActionError(
                is_error=True,
                error_code="CONTRACT_NOT_FOUND",
                error_message=f"Contract {validated_contract_id} not found or you don't have access to it.",
                details={"contract_id": validated_contract_id, "error_details": e.message},
            )
        except ApiError as e:
            logger.error(f"[UPDATE_METADATA] API error: {e.message}")
            return MetadataActionError(
                is_error=True,
                error_code="API_ERROR",
                error_message=f"Failed to fetch metadata for contract {validated_contract_id}. Error: {e.message}",
                details={
                    "contract_id": validated_contract_id,
                    "recoverable": e.recoverable,
                    "error_details": e.message,
                },
            )

        if not isinstance(response_data, dict):
            error_msg = (
                f"Invalid response format from API: expected dict, got {type(response_data).__name__}. "
                f"Cannot process metadata for contract {validated_contract_id}."
            )
            logger.error(f"[UPDATE_METADATA] {error_msg}")
            return MetadataActionError(
                is_error=True,
                error_code="INVALID_RESPONSE_FORMAT",
                error_message=error_msg,
                details={
                    "contract_id": validated_contract_id,
                    "received_type": type(response_data).__name__,
                },
            )

        response_list = response_data.get("response", [])
        if not isinstance(response_list, list):
            error_msg = (
                f"Invalid response format from API: 'response' must be a list, got {type(response_list).__name__}. "
                f"Cannot process metadata for contract {validated_contract_id}."
            )
            logger.error(f"[UPDATE_METADATA] {error_msg}")
            return MetadataActionError(
                is_error=True,
                error_code="INVALID_RESPONSE_FORMAT",
                error_message=error_msg,
                details={
                    "contract_id": validated_contract_id,
                    "received_type": type(response_list).__name__,
                },
            )

        logger.info(
            f"[UPDATE_METADATA] Found {len(response_list)} metadata items for contract_id={validated_contract_id}"
        )
        logger.debug(
            f"[UPDATE_METADATA] Building metadata maps from {len(response_list)} items"
        )
        for item in response_list:
            if not isinstance(item, dict):
                logger.warning(
                    f"[UPDATE_METADATA] Skipping invalid metadata item: expected dict, got {type(item).__name__}"
                )
                continue

            key_obj = item.get("key", {})
            if not isinstance(key_obj, dict):
                logger.warning(
                    f"[UPDATE_METADATA] Skipping metadata item with invalid key object: expected dict, got {type(key_obj).__name__}"
                )
                continue

            key_id = key_obj.get("id")
            item_id = item.get("id")

            metadata_info = {
                "key_id": key_id,
                "metadata_id": item_id,
                "key_name": key_obj.get("name", f"Key ID {key_id}"),
                "key_label": key_obj.get("label"),
                "current_value": item.get("value", ""),
                "current_date_value": item.get("dateValue"),
                "is_locked": item.get("lock", False),
                "status": item.get("status"),
            }

            # Map by metadata_id if it exists (for UPDATE operations)
            if item_id:
                current_metadata_map[item_id] = metadata_info

            # Map by key_id (for both UPDATE and CREATE operations)
            if key_id:
                key_metadata_map[key_id] = metadata_info

        logger.debug(
            f"[UPDATE_METADATA] Built metadata maps: {len(current_metadata_map)} items with metadata_id, "
            f"{len(key_metadata_map)} items with key_id"
        )
    except ValidationError as e:
        logger.error(f"[UPDATE_METADATA] Validation error: {e.message}")
        return MetadataActionError(
            is_error=True,
            error_code="VALIDATION_ERROR",
            error_message=f"Validation error: {e.message}",
            details={"contract_id": validated_contract_id, "validation_details": e.details},
        )
    except (ApiError, NotFoundError) as e:
        logger.error(f"[UPDATE_METADATA] API error: {e.message}")
        return MetadataActionError(
            is_error=True,
            error_code="METADATA_FETCH_ERROR",
            error_message=f"Error fetching metadata: {e.message}. Could not validate metadata IDs.",
            details={
                "contract_id": validated_contract_id,
                "recoverable": getattr(e, "recoverable", False),
            },
        )
    except Exception as e:
        error_msg = (
            f"Unexpected error fetching metadata for contract {validated_contract_id}: {str(e)}. "
            f"Error type: {type(e).__name__}. "
            f"Could not validate metadata IDs."
        )
        logger.exception(f"[UPDATE_METADATA] {error_msg}")
        return MetadataActionError(
            is_error=True,
            error_code="UNEXPECTED_ERROR",
            error_message=error_msg,
            details={
                "contract_id": validated_contract_id,
                "error_type": type(e).__name__,
            },
        )

    # Check if any updates involve person metadata and fetch user list if needed
    valid_user_ids: set[int] = set()
    name_to_id_map: dict[str, int] = {}
    has_person_updates = False
    for update in validated_updates:
        if update.value is not None:
            # Check if this update is for person metadata
            if update.metadata_id:
                metadata_info = current_metadata_map.get(update.metadata_id)
                if metadata_info and _is_person_field(
                    metadata_info.get("key_id") or 0,
                    metadata_info.get("key_label") or "",
                ):
                    has_person_updates = True
                    break
            elif update.key_id:
                if _is_person_field(update.key_id, ""):
                    has_person_updates = True
                    break

    if has_person_updates:
        logger.info(
            "[UPDATE_METADATA] Person metadata updates detected, fetching user list for validation and name resolution"
        )
        # Fetch both valid IDs and name mapping
        valid_user_ids = await _get_valid_user_ids(conpass_api_service)
        name_to_id_map = await _get_user_list_with_names(conpass_api_service)
        if not valid_user_ids:
            logger.warning(
                "[UPDATE_METADATA] Could not fetch user list. Person ID validation will be skipped."
            )
        if not name_to_id_map:
            logger.warning(
                "[UPDATE_METADATA] Could not build name-to-ID mapping. Name resolution will be limited."
            )

    # Process each update
    logger.info(
        f"[UPDATE_METADATA] Processing {len(validated_updates)} update item(s) for contract_id={validated_contract_id}"
    )
    for idx, update in enumerate(validated_updates, 1):
        metadata_id = update.metadata_id
        key_id = update.key_id
        value = update.value
        date_value = update.date_value
        lock = update.lock

        logger.debug(
            f"[UPDATE_METADATA] Processing update {idx}/{len(validated_updates)}: "
            f"metadata_id={metadata_id}, key_id={key_id}, "
            f"has_value={value is not None}, has_date_value={date_value is not None}, "
            f"has_lock={lock is not None}"
        )

        # Determine operation type and get metadata info
        current_info = None
        is_create_operation = False

        if metadata_id is not None:
            # UPDATE operation: use metadata_id
            current_info = current_metadata_map.get(metadata_id)
            if not current_info:
                available_ids = list(current_metadata_map.keys())[
                    :10
                ]  # Limit to first 10 for readability
                available_ids_str = ", ".join(str(id) for id in available_ids)
                if len(current_metadata_map) > 10:
                    available_ids_str += f" (and {len(current_metadata_map) - 10} more)"
                error_msg = (
                    f"Metadata ID {metadata_id} not found in contract {validated_contract_id}. "
                    f"Available metadata IDs: {available_ids_str if available_ids else 'none'}. "
                    f"Use read_metadata tool to see all available metadata for this contract."
                )
                logger.warning(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
                errors.append(error_msg)
                continue
        elif key_id is not None:
            # CREATE operation: use key_id
            current_info = key_metadata_map.get(key_id)
            if not current_info:
                available_key_ids = list(key_metadata_map.keys())[
                    :10
                ]  # Limit to first 10 for readability
                available_key_ids_str = ", ".join(str(id) for id in available_key_ids)
                if len(key_metadata_map) > 10:
                    available_key_ids_str += f" (and {len(key_metadata_map) - 10} more)"
                error_msg = (
                    f"Metadata key ID {key_id} not found or not available for contract {validated_contract_id}. "
                    f"Available key IDs: {available_key_ids_str if available_key_ids else 'none'}. "
                    f"Use read_metadata tool to see all available metadata keys for this contract."
                )
                logger.warning(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
                errors.append(error_msg)
                continue

            # Check if this key already has a metadata record
            if current_info.get("metadata_id") is not None:
                error_msg = (
                    f"Metadata key ID {key_id} already has a metadata record (metadata_id: {current_info['metadata_id']}). "
                    f"To update it, use metadata_id={current_info['metadata_id']} instead of key_id. "
                    f"Use key_id only when creating new metadata (when id is null)."
                )
                logger.warning(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
                errors.append(error_msg)
                continue

            is_create_operation = True
            logger.info(
                f"[UPDATE_METADATA] Update {idx}: CREATE operation for key_id={key_id}"
            )
        else:
            error_msg = "Either metadata_id or key_id must be provided."
            logger.error(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
            errors.append(error_msg)
            continue

        # Extract key_id from current_info (it's always there for fixed metadata)
        resolved_key_id = current_info.get("key_id") or key_id
        key_name = current_info.get("key_name", f"Key ID {resolved_key_id}")
        key_label = current_info.get("key_label")
        current_value = current_info.get("current_value", "")
        current_date_value = current_info.get("current_date_value")
        is_locked = current_info.get("is_locked", False)
        metadata_status = current_info.get("status")

        # Detect field type using resolved key_id
        field_type = _get_metadata_field_type(resolved_key_id or 0, key_label or "")
        is_date_field = _is_date_field(resolved_key_id or 0, key_label or "")
        is_contract_type_field = _is_contract_type_field(
            resolved_key_id or 0, key_label or ""
        )
        is_person_metadata = _is_person_field(resolved_key_id or 0, key_label or "")

        logger.debug(
            f"[UPDATE_METADATA] Update {idx}: Found metadata '{key_name}' (label={key_label}, "
            f"key_id={key_id}, field_type={field_type}), "
            f"current_status={metadata_status}, is_locked={is_locked}, "
            f"is_person_metadata={is_person_metadata}, is_contract_type={is_contract_type_field}, "
            f"is_date_field={is_date_field}, is_create={is_create_operation}, "
            f"current_value='{current_value[:50] if current_value else ''}{'...' if current_value and len(current_value) > 50 else ''}', "
            f"current_date_value={current_date_value}"
        )

        # Validate metadata status (must be ENABLE = 1)
        if metadata_status != 1:
            error_msg = (
                f"Metadata '{key_name}' (ID: {metadata_id}) is not in ENABLE status "
                f"(current status: {metadata_status})."
            )
            logger.warning(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
            errors.append(error_msg)
            continue

        # Type-specific validation: Date fields must use date_value, not value
        if is_date_field:
            if value is not None:
                error_msg = (
                    f"Metadata '{key_name}' (ID: {metadata_id}) is a date field and must use "
                    f"'date_value', not 'value'. Please use date_value instead."
                )
                logger.warning(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
                errors.append(error_msg)
                continue

            if date_value is not None and not _validate_date_format(date_value):
                error_msg = (
                    f"Invalid date format for metadata '{key_name}' (ID: {metadata_id}): '{date_value}'. "
                    "Must be YYYY-MM-DD format."
                )
                logger.warning(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
                errors.append(error_msg)
                continue
        else:
            # Text fields (including contract type and person) must use value, not date_value
            if date_value is not None:
                error_msg = (
                    f"Metadata '{key_name}' (ID: {metadata_id}) is a text field and must use "
                    f"'value', not 'date_value'. Please use value instead."
                )
                logger.warning(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
                errors.append(error_msg)
                continue

        # Validate contract type value
        if is_contract_type_field and value is not None:
            is_valid, error_msg = _validate_contract_type_value(value)
            if not is_valid:
                logger.warning(
                    f"[UPDATE_METADATA] Update {idx}: Contract type validation failed for "
                    f"metadata '{key_name}' (ID: {metadata_id}): {error_msg}"
                )
                errors.append(
                    f"Invalid contract type for metadata '{key_name}' (ID: {metadata_id}): {error_msg}"
                )
                continue

        # Validate value length (for text fields)
        if value is not None and len(value) > 255:
            error_msg = (
                f"Value for metadata '{key_name}' (ID: {metadata_id}) exceeds 255 characters "
                f"(length: {len(value)})."
            )
            logger.warning(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
            errors.append(error_msg)
            continue

        # Enhanced validation for person metadata with name resolution
        if is_person_metadata and value is not None:
            # Resolve person names to IDs (handles both names and numeric IDs)
            resolved_person_ids, unresolved_names = await _resolve_person_names_to_ids(
                conpass_api_service, value, name_to_id_map
            )

            # Check if there were unresolved names
            if unresolved_names:
                # Check if API was unavailable (empty name_to_id_map and no valid_user_ids)
                api_unavailable = not name_to_id_map and not valid_user_ids
                if api_unavailable:
                    error_msg = (
                        f"Person metadata '{key_name}' (ID: {metadata_id}) contains names that could not be resolved: "
                        f"{', '.join(unresolved_names)}. "
                        f"The user list API is currently unavailable. Please use numeric person IDs instead (e.g., '1,2,3'). "
                        f"If you don't know the person ID, please contact your administrator or try again later when the API is available."
                    )
                else:
                    error_msg = (
                        f"Person metadata '{key_name}' (ID: {metadata_id}) contains names that could not be resolved to user IDs: "
                        f"{', '.join(unresolved_names)}. "
                        f"Please use valid person names or numeric person IDs (e.g., '1,2,3' or 'John Doe, Jane Smith')."
                    )
                logger.warning(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
                errors.append(error_msg)
                continue

            # If empty string, that's valid (removes all persons)
            if value.strip() == "":
                # Keep value as empty string
                pass
            elif not resolved_person_ids:
                # No valid IDs resolved
                error_msg = (
                    f"Person metadata '{key_name}' (ID: {metadata_id}) could not resolve any valid person IDs from: '{value}'. "
                    f"Please use valid person names or numeric person IDs (e.g., '1,2,3' or 'John Doe, Jane Smith')."
                )
                logger.warning(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
                errors.append(error_msg)
                continue
            else:
                # Validate resolved person IDs exist in the system
                if valid_user_ids:
                    invalid_person_ids = [
                        pid for pid in resolved_person_ids if pid not in valid_user_ids
                    ]
                    if invalid_person_ids:
                        error_msg = (
                            f"Person metadata '{key_name}' (ID: {metadata_id}) contains person IDs that do not exist: "
                            f"{', '.join(str(pid) for pid in invalid_person_ids)}. "
                            f"Please use valid person IDs from your account."
                        )
                        logger.warning(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
                        errors.append(error_msg)
                        continue

                    # Update value to use resolved IDs (comma-separated string)
                    value = ",".join(str(pid) for pid in resolved_person_ids)
                    logger.info(
                        f"[UPDATE_METADATA] Update {idx}: Resolved person names to IDs: {value}"
                    )
                else:
                    # If we couldn't fetch user list, log a warning but don't block
                    # Still use the resolved IDs (they were resolved from names)
                    if resolved_person_ids:
                        value = ",".join(str(pid) for pid in resolved_person_ids)
                        logger.warning(
                            f"[UPDATE_METADATA] Update {idx}: Could not validate person IDs exist "
                            f"for metadata '{key_name}' (ID: {metadata_id}) because user list could not be fetched. "
                            f"Proceeding with resolved IDs: {value}"
                        )

        # Check if at least one field is being updated
        if value is None and date_value is None and lock is None:
            id_desc = (
                f"key_id={key_id}"
                if is_create_operation
                else f"metadata_id={metadata_id}"
            )
            error_msg = (
                f"No update fields provided for metadata '{key_name}' ({id_desc})."
            )
            logger.warning(f"[UPDATE_METADATA] Update {idx}: {error_msg}")
            errors.append(error_msg)
            continue

        # Handle locked metadata: if locked and trying to update value/date, unlock first
        # (only for UPDATE operations, CREATE operations don't have locks)
        if (
            not is_create_operation
            and is_locked
            and (value is not None or date_value is not None)
        ):
            logger.info(
                f"[UPDATE_METADATA] Update {idx}: Metadata '{key_name}' (ID: {metadata_id}) is locked. "
                "Creating unlock step followed by update step."
            )
            # Create unlock step first
            unlock_item = MetadataItem(
                metadata_id=metadata_id,
                key_id=None,
                value=None,
                date_value=None,
                lock=False,  # Unlock
                key_name=key_name,
                key_label=key_label,
                current_value=current_value,
                current_date_value=current_date_value,
                current_lock=True,
            )
            metadata_items.append(unlock_item)
            logger.debug(
                f"[UPDATE_METADATA] Update {idx}: Added unlock step for metadata_id={metadata_id}"
            )

            # Then create update step
            update_item = MetadataItem(
                metadata_id=metadata_id,
                key_id=None,
                value=value,
                date_value=date_value,
                lock=lock,  # Can set lock status in same update
                key_name=key_name,
                key_label=key_label,
                current_value=current_value,
                current_date_value=current_date_value,
                current_lock=False,  # Will be unlocked by previous step
            )
            metadata_items.append(update_item)
            logger.debug(
                f"[UPDATE_METADATA] Update {idx}: Added update step for metadata_id={metadata_id}, "
                f"value='{value[:50] if value else None}{'...' if value and len(value) > 50 else ''}', "
                f"date_value={date_value}, lock={lock}"
            )
        else:
            # Normal update (not locked, or only updating lock status) or CREATE operation
            operation_desc = "CREATE" if is_create_operation else "UPDATE"
            id_desc = (
                f"key_id={key_id}"
                if is_create_operation
                else f"metadata_id={metadata_id}"
            )
            logger.debug(
                f"[UPDATE_METADATA] Update {idx}: Creating {operation_desc} operation for {id_desc}, "
                f"is_locked={is_locked}"
            )
            update_item = MetadataItem(
                metadata_id=metadata_id,
                key_id=key_id,
                value=value,
                date_value=date_value,
                lock=lock,
                key_name=key_name,
                key_label=key_label,
                current_value=current_value,
                current_date_value=current_date_value,
                current_lock=is_locked,
            )
            metadata_items.append(update_item)
            logger.debug(
                f"[UPDATE_METADATA] Update {idx}: Added {operation_desc} item for {id_desc}, "
                f"value='{value[:50] if value else None}{'...' if value and len(value) > 50 else ''}', "
                f"date_value={date_value}, lock={lock}"
            )

    logger.info(
        f"[UPDATE_METADATA] Processed all updates for contract_id={validated_contract_id}. "
        f"Created {len(metadata_items)} metadata item(s), "
        f"encountered {len(errors)} error(s)"
    )

    if not metadata_items:
        if errors:
            error_message = f"All {len(errors)} update item(s) failed validation"
        else:
            error_message = (
                "No valid metadata items to update. "
                "Ensure each update item has either metadata_id (for updates) or key_id (for creates), "
                "and at least one field to update (value, date_value, or lock)."
            )
        logger.error(
            f"[UPDATE_METADATA] Failed for contract_id={validated_contract_id}: {error_message}"
        )
        return MetadataActionError(
            is_error=True,
            error_code="NO_VALID_METADATA_ITEMS",
            error_message=error_message,
            details={
                "contract_id": validated_contract_id,
                "validation_errors": errors if errors else None,
            },
        )

    error_message = None
    if errors:
        error_message = (
            f"Completed with {len(errors)} error(s) out of {len(validated_updates)} update(s). "
            f"Errors: {'; '.join(errors)}"
        )
        logger.warning(
            f"[UPDATE_METADATA] Completed with warnings for contract_id={validated_contract_id}: "
            f"{error_message}"
        )

    # Count unique metadata items (excluding unlock steps) for logging
    unique_metadata_ids = set()
    for item in metadata_items:
        if item.metadata_id and (
            item.value is not None
            or item.date_value is not None
            or item.lock is not None
        ):
            unique_metadata_ids.add(item.metadata_id)

    logger.info(
        f"[UPDATE_METADATA] Successful for contract_id={validated_contract_id}: "
        f"{len(unique_metadata_ids)} unique metadata item(s) will be updated, "
        f"total action items: {len(metadata_items)}"
    )

    # Generate JWT token for the action
    logger.info(
        f"[UPDATE_METADATA] All validations passed. Creating action template for contract_id={validated_contract_id}"
    )

    hashed_metadata_action = generate_jwt_token(
        action=UpdateMetadataAction(
            contract_id=validated_contract_id,
            metadata_items=metadata_items,
            title=UPDATE_METADATA_TITLE,
            confirmation_api_url=CONFIRMATION_API_URL,
            cancel_api_url=CANCEL_API_URL,
            status="pending",
            error_message=error_message,
        )
    )

    return UpdateMetadataAction(
        contract_id=validated_contract_id,
        metadata_items=metadata_items,
        title=UPDATE_METADATA_TITLE,
        confirmation_api_url=CONFIRMATION_API_URL,
        cancel_api_url=CANCEL_API_URL,
        status="pending",
        error_message=error_message,
        jwt_token=hashed_metadata_action,
    )
