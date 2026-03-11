from typing import List, Dict, Any, Optional

from app.core.logging_config import get_logger
from app.services.conpass_api_service import ConpassApiService
from app.services.chatbot.tools.metadata_crud.error_handling import (
    ValidationError,
    ApiError,
    NotFoundError,
    format_error_response,
    format_success_response,
    validate_contract_ids,
    validate_directory_id,
    handle_api_response,
)

logger = get_logger(__name__)


async def read_metadata(
    conpass_api_service: ConpassApiService,
    contract_ids: Optional[List[int]] = None,
    directory_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Read metadata information. Supports three scenarios:
    1. Get contract metadata: Provide contract_ids (list of contract IDs)
    2. Get metadata keys for a directory: Provide directory_id
    3. Get all metadata keys in the system: Provide neither (or both None)

    Args:
        conpass_api_service: The ConPass API service instance
        contract_ids: Optional list of contract IDs to get metadata for
        directory_id: Optional directory ID to get metadata keys for

    Returns:
        List of dictionaries containing metadata information or error responses
    """
    logger.info(
        f"[READ_METADATA] Called with contract_ids={contract_ids}, directory_id={directory_id}"
    )

    # Validate that both parameters are not provided simultaneously
    if contract_ids is not None and directory_id is not None:
        error = ValidationError(
            "Cannot provide both contract_ids and directory_id. "
            "Provide contract_ids to read contract metadata, "
            "directory_id to read directory metadata keys, "
            "or neither to read all metadata keys in the system.",
            details={
                "contract_ids_provided": contract_ids is not None,
                "directory_id_provided": directory_id is not None,
            },
        )
        logger.error(f"[READ_METADATA] Validation error: {error.message}")
        return [format_error_response(error)]

    # Scenario 1: Get metadata keys for a specific directory
    if directory_id is not None:
        try:
            validated_directory_id = validate_directory_id(directory_id)
        except ValidationError as e:
            logger.error(f"[READ_METADATA] Validation error: {e.message}")
            return [format_error_response(e, context={"directory_id": directory_id})]

        logger.info(
            f"[READ_METADATA] Fetching metadata keys for directory_id={validated_directory_id}"
        )
        try:
            response = await conpass_api_service.get_directory_metadata_settings(
                validated_directory_id
            )

            try:
                response_data = handle_api_response(
                    response,
                    f"fetching metadata keys for directory {validated_directory_id}",
                    context={"directory_id": validated_directory_id},
                )
            except (ApiError, NotFoundError) as e:
                logger.error(f"[READ_METADATA] API error: {e.message}")
                return [
                    format_error_response(
                        e, context={"directory_id": validated_directory_id}
                    )
                ]

            if not isinstance(response_data, dict):
                error = ApiError(
                    f"Invalid response format from API: expected dict, got {type(response_data).__name__}",
                    details={
                        "operation": "get_directory_metadata_settings",
                        "directory_id": validated_directory_id,
                        "response_type": type(response_data).__name__,
                    },
                    recoverable=False,
                )
                logger.error(f"[READ_METADATA] {error.message}")
                return [
                    format_error_response(
                        error, context={"directory_id": validated_directory_id}
                    )
                ]

            if "response" not in response_data:
                error = ApiError(
                    "Invalid response format from API: missing 'response' key in response data",
                    details={
                        "operation": "get_directory_metadata_settings",
                        "directory_id": validated_directory_id,
                        "response_keys": list(response_data.keys())
                        if isinstance(response_data, dict)
                        else None,
                    },
                    recoverable=False,
                )
                logger.error(f"[READ_METADATA] {error.message}")
                return [
                    format_error_response(
                        error, context={"directory_id": validated_directory_id}
                    )
                ]

            response_dict = response_data.get("response", {})
            if not isinstance(response_dict, dict):
                error = ApiError(
                    f"Invalid response format from API: 'response' must be a dict, got {type(response_dict).__name__}",
                    details={
                        "operation": "get_directory_metadata_settings",
                        "directory_id": validated_directory_id,
                        "response_type": type(response_dict).__name__,
                    },
                    recoverable=False,
                )
                logger.error(f"[READ_METADATA] {error.message}")
                return [
                    format_error_response(
                        error, context={"directory_id": validated_directory_id}
                    )
                ]

            default_list = response_dict.get("default_list", [])
            free_list = response_dict.get("free_list", [])

            if not isinstance(default_list, list):
                error = ApiError(
                    f"Invalid response format from API: 'default_list' must be a list, got {type(default_list).__name__}",
                    details={
                        "operation": "get_directory_metadata_settings",
                        "directory_id": validated_directory_id,
                        "default_list_type": type(default_list).__name__,
                    },
                    recoverable=False,
                )
                logger.error(f"[READ_METADATA] {error.message}")
                return [
                    format_error_response(
                        error, context={"directory_id": validated_directory_id}
                    )
                ]

            if not isinstance(free_list, list):
                error = ApiError(
                    f"Invalid response format from API: 'free_list' must be a list, got {type(free_list).__name__}",
                    details={
                        "operation": "get_directory_metadata_settings",
                        "directory_id": validated_directory_id,
                        "free_list_type": type(free_list).__name__,
                    },
                    recoverable=False,
                )
                logger.error(f"[READ_METADATA] {error.message}")
                return [
                    format_error_response(
                        error, context={"directory_id": validated_directory_id}
                    )
                ]

            metadata_keys = []

            # Process DEFAULT metadata keys
            for idx, key in enumerate(default_list):
                if not isinstance(key, dict):
                    logger.warning(
                        f"[READ_METADATA] Skipping invalid key at index {idx} in default_list: "
                        f"expected dict, got {type(key).__name__}"
                    )
                    continue

                metadata_keys.append(
                    {
                        "key_id": key.get("id"),
                        "key_name": key.get("name"),
                        "key_type": "DEFAULT",
                        "type": key.get("type"),
                        "is_visible": key.get("is_visible", True),
                        "meta_key_directory_id": key.get("meta_key_directory_id"),
                    }
                )

            # Process FREE metadata keys
            for idx, key in enumerate(free_list):
                if not isinstance(key, dict):
                    logger.warning(
                        f"[READ_METADATA] Skipping invalid key at index {idx} in free_list: "
                        f"expected dict, got {type(key).__name__}"
                    )
                    continue

                metadata_keys.append(
                    {
                        "key_id": key.get("id"),
                        "key_name": key.get("name"),
                        "key_type": "FREE",
                        "type": key.get("type"),
                        "is_visible": key.get("is_visible", True),
                        "meta_key_directory_id": key.get("meta_key_directory_id"),
                    }
                )

            logger.info(
                f"[READ_METADATA] Successfully fetched {len(metadata_keys)} metadata keys "
                f"for directory_id={validated_directory_id}"
            )
            return [
                format_success_response(
                    {
                        "directory_id": validated_directory_id,
                        "metadata_keys": metadata_keys,
                        "default_count": len(default_list),
                        "free_count": len(free_list),
                    }
                )
            ]
        except ValidationError as e:
            logger.error(f"[READ_METADATA] Validation error: {e.message}")
            return [format_error_response(e, context={"directory_id": directory_id})]
        except (ApiError, NotFoundError) as e:
            logger.error(f"[READ_METADATA] API error: {e.message}")
            return [format_error_response(e, context={"directory_id": directory_id})]
        except Exception as e:
            error = ApiError(
                f"Unexpected error fetching metadata keys for directory {directory_id}: {str(e)}",
                details={
                    "operation": "get_directory_metadata_settings",
                    "directory_id": directory_id,
                    "exception_type": type(e).__name__,
                },
                recoverable=False,
            )
            logger.exception(f"[READ_METADATA] {error.message}")
            return [
                format_error_response(error, context={"directory_id": directory_id})
            ]

    # Scenario 2: Get contract metadata (if contract_ids provided)
    if contract_ids is not None:
        try:
            validated_contract_ids = validate_contract_ids(contract_ids)
        except ValidationError as e:
            logger.error(f"[READ_METADATA] Validation error: {e.message}")
            return [format_error_response(e, context={"contract_ids": contract_ids})]

        metadata = []
        for idx, contract_id in enumerate(validated_contract_ids, 1):
            logger.info(
                f"[READ_METADATA] Processing contract {idx}/{len(validated_contract_ids)}: contract_id={contract_id}"
            )
            # Initialize directory_id before try block so it's available in exception handler
            directory_id = None
            try:
                # Fetch contract information to get directory ID (optional, for context)
                try:
                    logger.debug(
                        f"[READ_METADATA] Calling get_contract API for contract_id={contract_id} to get directory ID"
                    )
                    contract_response = await conpass_api_service.get_contract(
                        contract_id
                    )
                    if contract_response.status == "success":
                        try:
                            contract_data = handle_api_response(
                                contract_response,
                                f"fetching contract {contract_id} for directory ID",
                                context={"contract_id": contract_id},
                            )
                            if (
                                isinstance(contract_data, dict)
                                and "response" in contract_data
                            ):
                                contract_info = contract_data.get("response", {})
                                if (
                                    isinstance(contract_info, dict)
                                    and "directory" in contract_info
                                ):
                                    directory = contract_info.get("directory", {})
                                    if isinstance(directory, dict):
                                        # Use parent as directory_id if it exists, otherwise use id
                                        if (
                                            "parent" in directory
                                            and directory.get("parent") is not None
                                        ):
                                            directory_id = directory.get("parent")
                                        elif "id" in directory:
                                            directory_id = directory.get("id")

                                        if directory_id is not None:
                                            logger.info(
                                                f"[READ_METADATA] Found directory_id={directory_id} for contract_id={contract_id}"
                                            )
                        except (ApiError, NotFoundError):
                            # Directory ID fetch is optional, continue without it
                            logger.debug(
                                f"[READ_METADATA] Could not fetch directory ID for contract_id={contract_id}, continuing"
                            )
                except Exception as e:
                    # Directory ID fetch is optional, log warning but continue
                    logger.warning(
                        f"[READ_METADATA] Failed to fetch directory ID for contract_id={contract_id}: {e}"
                    )

                logger.debug(
                    f"[READ_METADATA] Calling get_contract_metadata API for contract_id={contract_id}"
                )
                response = await conpass_api_service.get_contract_metadata(contract_id)

                try:
                    response_data = handle_api_response(
                        response,
                        f"fetching metadata for contract {contract_id}",
                        context={"contract_id": contract_id},
                    )
                except NotFoundError as e:
                    logger.error(f"[READ_METADATA] Not found error: {e.message}")
                    error_response = format_error_response(
                        e,
                        context={
                            "contract_id": contract_id,
                            "directory_id": directory_id,
                        },
                    )
                    metadata.append(error_response)
                    continue
                except ApiError as e:
                    logger.error(f"[READ_METADATA] API error: {e.message}")
                    error_response = format_error_response(
                        e,
                        context={
                            "contract_id": contract_id,
                            "directory_id": directory_id,
                        },
                    )
                    metadata.append(error_response)
                    continue

                if not isinstance(response_data, dict):
                    error = ApiError(
                        f"Invalid response format from API: expected dict, got {type(response_data).__name__}",
                        details={
                            "operation": "get_contract_metadata",
                            "contract_id": contract_id,
                            "response_type": type(response_data).__name__,
                        },
                        recoverable=False,
                    )
                    logger.error(f"[READ_METADATA] {error.message}")
                    error_response = format_error_response(
                        error,
                        context={
                            "contract_id": contract_id,
                            "directory_id": directory_id,
                        },
                    )
                    metadata.append(error_response)
                    continue

                if "response" not in response_data:
                    error = ApiError(
                        "Invalid response format from API: missing 'response' key in response data",
                        details={
                            "operation": "get_contract_metadata",
                            "contract_id": contract_id,
                            "response_keys": list(response_data.keys())
                            if isinstance(response_data, dict)
                            else None,
                        },
                        recoverable=False,
                    )
                    logger.error(f"[READ_METADATA] {error.message}")
                    error_response = format_error_response(
                        error,
                        context={
                            "contract_id": contract_id,
                            "directory_id": directory_id,
                        },
                    )
                    metadata.append(error_response)
                    continue

                response_list = response_data.get("response", [])
                logger.debug(
                    f"[READ_METADATA] Extracted response list for contract_id={contract_id}: "
                    f"type={type(response_list).__name__}, length={len(response_list) if isinstance(response_list, list) else 'N/A'}"
                )

                if not isinstance(response_list, list):
                    error = ApiError(
                        f"Invalid response format from API: 'response' must be a list, got {type(response_list).__name__}",
                        details={
                            "operation": "get_contract_metadata",
                            "contract_id": contract_id,
                            "response_type": type(response_list).__name__,
                        },
                        recoverable=False,
                    )
                    logger.error(f"[READ_METADATA] {error.message}")
                    error_response = format_error_response(
                        error,
                        context={
                            "contract_id": contract_id,
                            "directory_id": directory_id,
                        },
                    )
                    metadata.append(error_response)
                    continue

                extracted_metadata = []
                logger.debug(
                    f"[READ_METADATA] Processing {len(response_list)} metadata entries "
                    f"for contract_id={contract_id}"
                )

                for entry_idx, entry in enumerate(response_list, 1):
                    if not isinstance(entry, dict):
                        logger.warning(
                            f"[READ_METADATA] Skipping non-dict entry {entry_idx} "
                            f"in metadata for contract_id={contract_id}: type={type(entry).__name__}"
                        )
                        continue

                    metadata_id = ""
                    key_id = ""
                    key_name = ""
                    key_label = ""
                    value = ""
                    date_value = ""
                    is_locked = False
                    try:
                        metadata_id = entry.get("id")
                        key_obj = entry.get("key")
                        if isinstance(key_obj, dict):
                            key_id = key_obj.get("id", "")
                            key_name = key_obj.get("name", "")
                            key_label = key_obj.get("label", "")
                        value = entry.get("value", "")
                        date_value = entry.get("dateValue", "")
                        is_locked = entry.get("lock", False)

                        logger.debug(
                            f"[READ_METADATA] Extracted entry {entry_idx} for contract_id={contract_id}: "
                            f"metadata_id={metadata_id}, key_id={key_id}, key_name={key_name}, "
                            f"key_label={key_label}, has_value={bool(value)}, "
                            f"has_date_value={bool(date_value)}, is_locked={is_locked}"
                        )
                    except (AttributeError, TypeError) as e:
                        logger.warning(
                            f"[READ_METADATA] Error extracting metadata from entry {entry_idx} "
                            f"for contract_id={contract_id}: {e}, entry={entry}"
                        )

                    extracted_metadata.append(
                        {
                            "metadata_id": metadata_id,
                            "key_id": key_id,
                            "key_name": key_name,
                            "key_label": key_label,
                            "value": value,
                            "date_value": date_value,
                            "is_locked": is_locked,
                        }
                    )

                logger.info(
                    f"[READ_METADATA] Successfully extracted {len(extracted_metadata)} metadata entries "
                    f"for contract_id={contract_id}"
                )
                result_data = {
                    "contract_id": contract_id,
                    "metadata": extracted_metadata,
                }
                if directory_id is not None:
                    result_data["directory_id"] = directory_id
                metadata.append(
                    format_success_response(
                        result_data,
                        context={
                            "contract_id": contract_id,
                            "directory_id": directory_id,
                        },
                    )
                )
            except ValidationError as e:
                logger.error(f"[READ_METADATA] Validation error: {e.message}")
                error_response = format_error_response(
                    e,
                    context={"contract_id": contract_id, "directory_id": directory_id},
                )
                metadata.append(error_response)
            except (ApiError, NotFoundError) as e:
                logger.error(f"[READ_METADATA] API error: {e.message}")
                error_response = format_error_response(
                    e,
                    context={"contract_id": contract_id, "directory_id": directory_id},
                )
                metadata.append(error_response)
            except Exception as e:
                error = ApiError(
                    f"Unexpected error processing metadata for contract {contract_id}: {str(e)}",
                    details={
                        "operation": "get_contract_metadata",
                        "contract_id": contract_id,
                        "exception_type": type(e).__name__,
                    },
                    recoverable=False,
                )
                logger.exception(f"[READ_METADATA] {error.message}")
                error_response = format_error_response(
                    error,
                    context={"contract_id": contract_id, "directory_id": directory_id},
                )
                metadata.append(error_response)

        logger.info(
            f"[READ_METADATA] Completed processing {len(validated_contract_ids)} contract(s). "
            f"Returning {len(metadata)} result(s)"
        )
        return metadata

    # Scenario 3: Get all metadata keys in the system (when neither contract_ids nor directory_id provided)
    logger.info("[READ_METADATA] Fetching all metadata keys in the system")
    try:
        response = await conpass_api_service.get_all_metadata_keys()

        try:
            response_data = handle_api_response(
                response,
                "fetching all metadata keys",
            )
        except (ApiError, NotFoundError) as e:
            logger.error(f"[READ_METADATA] API error: {e.message}")
            return [format_error_response(e)]

        response_list = None
        if isinstance(response_data, list):
            response_list = response_data
        elif isinstance(response_data, dict) and "response" in response_data:
            response_list = response_data.get("response", [])

        if not isinstance(response_list, list):
            error = ApiError(
                f"Invalid response format from API: expected list, got {type(response_list).__name__}",
                details={
                    "operation": "get_all_metadata_keys",
                    "response_type": type(response_list).__name__,
                },
                recoverable=False,
            )
            logger.error(f"[READ_METADATA] {error.message}")
            return [format_error_response(error)]

        metadata_keys = []
        for idx, key in enumerate(response_list):
            if not isinstance(key, dict):
                logger.warning(
                    f"[READ_METADATA] Skipping invalid key at index {idx}: "
                    f"expected dict, got {type(key).__name__}"
                )
                continue

            key_type = "DEFAULT" if key.get("type") == 1 else "FREE"
            metadata_keys.append(
                {
                    "key_id": key.get("id"),
                    "key_name": key.get("name"),
                    "key_label": key.get("label", ""),
                    "key_type": key_type,
                    "type": key.get("type"),
                    "is_visible": key.get("is_visible", True),
                    "status": key.get("status"),
                    "account_id": key.get("accountId"),
                }
            )

        logger.info(
            f"[READ_METADATA] Successfully fetched {len(metadata_keys)} metadata keys "
            f"from the system"
        )
        return [
            format_success_response(
                {
                    "metadata_keys": metadata_keys,
                    "total_count": len(metadata_keys),
                }
            )
        ]
    except ValidationError as e:
        logger.error(f"[READ_METADATA] Validation error: {e.message}")
        return [format_error_response(e)]
    except (ApiError, NotFoundError) as e:
        logger.error(f"[READ_METADATA] API error: {e.message}")
        return [format_error_response(e)]
    except Exception as e:
        error = ApiError(
            f"Unexpected error fetching all metadata keys: {str(e)}",
            details={
                "operation": "get_all_metadata_keys",
                "exception_type": type(e).__name__,
            },
            recoverable=False,
        )
        logger.exception(f"[READ_METADATA] {error.message}")
        return [format_error_response(error)]
