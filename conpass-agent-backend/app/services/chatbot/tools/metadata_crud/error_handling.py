"""
Standardized error handling for metadata CRUD tools.

This module provides uniform error response structures and validation utilities
to ensure consistent error reporting across all metadata CRUD operations.
"""

from typing import Optional, Dict, Any, List
from app.core.logging_config import get_logger
import ast

logger = get_logger(__name__)


class MetadataCrudError(Exception):
    """
    Base exception class for metadata CRUD operations.
    All metadata CRUD errors should use this or a subclass.
    """

    def __init__(
        self,
        message: str,
        error_type: str,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = False,
    ):
        """
        Initialize metadata CRUD error.

        Args:
            message: Human-readable error message for the agent
            error_type: Error category (e.g., "validation", "api_error", "not_found")
            details: Additional error details (e.g., field names, IDs, available options)
            recoverable: Whether the error is recoverable (e.g., retryable API call)
        """
        self.message = message
        self.error_type = error_type
        self.details = details or {}
        self.recoverable = recoverable
        super().__init__(self.message)


class ValidationError(MetadataCrudError):
    """Error for validation failures."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "validation", details, recoverable=False)


class NotFoundError(MetadataCrudError):
    """Error for resource not found."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "not_found", details, recoverable=False)


class ApiError(MetadataCrudError):
    """Error for API call failures."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
    ):
        super().__init__(message, "api_error", details, recoverable)


def format_error_response(
    error: MetadataCrudError,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Format a standardized error response for metadata CRUD operations.

    Args:
        error: The metadata CRUD error
        context: Additional context (e.g., contract_id, directory_id)

    Returns:
        Standardized error response dictionary
    """
    response = {
        "error": True,
        "error_type": error.error_type,
        "error_message": error.message,
        "recoverable": error.recoverable,
    }

    if error.details:
        response["error_details"] = error.details

    if context:
        response["context"] = context

    return response


def format_success_response(
    data: Any,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Format a standardized success response for metadata CRUD operations.

    Args:
        data: The response data
        context: Additional context (e.g., contract_id, directory_id)

    Returns:
        Standardized success response dictionary
    """
    response = {
        "error": False,
        "data": data,
    }

    if context:
        response["context"] = context

    return response


def validate_contract_id(contract_id: Any) -> int:
    """
    Validate and convert contract_id to integer.

    Args:
        contract_id: Contract ID to validate

    Returns:
        Validated contract ID as integer

    Raises:
        ValidationError: If contract_id is invalid
    """
    if contract_id is None:
        raise ValidationError(
            "Contract ID is required.",
            details={"field": "contract_id", "provided": None},
        )

    try:
        contract_id_int = int(contract_id)
    except (ValueError, TypeError):
        raise ValidationError(
            f"Contract ID must be a valid integer, got: {type(contract_id).__name__}",
            details={"field": "contract_id", "provided": contract_id},
        )

    if contract_id_int <= 0:
        raise ValidationError(
            f"Contract ID must be a positive integer, got: {contract_id_int}",
            details={"field": "contract_id", "provided": contract_id_int},
        )

    return contract_id_int


def validate_directory_id(directory_id: Any) -> int:
    """
    Validate and convert directory_id to integer.

    Args:
        directory_id: Directory ID to validate

    Returns:
        Validated directory ID as integer

    Raises:
        ValidationError: If directory_id is invalid
    """
    if directory_id is None:
        raise ValidationError(
            "Directory ID is required.",
            details={"field": "directory_id", "provided": None},
        )

    try:
        directory_id_int = int(directory_id)
    except (ValueError, TypeError):
        raise ValidationError(
            f"Directory ID must be a valid integer, got: {type(directory_id).__name__}",
            details={"field": "directory_id", "provided": directory_id},
        )

    if directory_id_int <= 0:
        raise ValidationError(
            f"Directory ID must be a positive integer, got: {directory_id_int}",
            details={"field": "directory_id", "provided": directory_id_int},
        )

    return directory_id_int


def validate_contract_ids(contract_ids: Any) -> List[int]:
    """
    Validate and convert contract_ids list.

    Args:
        contract_ids: List of contract IDs to validate

    Returns:
        Validated list of contract IDs as integers

    Raises:
        ValidationError: If contract_ids is invalid
    """
    if contract_ids is None:
        raise ValidationError(
            "Contract IDs list is required.",
            details={"field": "contract_ids", "provided": None},
        )

    if not isinstance(contract_ids, list):
        raise ValidationError(
            f"Contract IDs must be a list, got: {type(contract_ids).__name__}",
            details={"field": "contract_ids", "provided": contract_ids},
        )

    if len(contract_ids) == 0:
        raise ValidationError(
            "Contract IDs list cannot be empty. Provide at least one contract ID.",
            details={"field": "contract_ids", "provided": []},
        )

    validated_ids = []
    for idx, contract_id in enumerate(contract_ids):
        try:
            validated_id = validate_contract_id(contract_id)
            validated_ids.append(validated_id)
        except ValidationError as e:
            raise ValidationError(
                f"Invalid contract ID at index {idx}: {e.message}",
                details={
                    "field": "contract_ids",
                    "index": idx,
                    "provided": contract_id,
                    "nested_error": e.details,
                },
            )

    return validated_ids


def validate_metadata_key_id(key_id: Any, field_name: str = "key_id") -> int:
    """
    Validate and convert metadata key_id to integer.

    Args:
        key_id: Key ID to validate
        field_name: Name of the field for error messages

    Returns:
        Validated key ID as integer

    Raises:
        ValidationError: If key_id is invalid
    """
    if key_id is None:
        raise ValidationError(
            f"{field_name} is required.",
            details={"field": field_name, "provided": None},
        )

    try:
        key_id_int = int(key_id)
    except (ValueError, TypeError):
        raise ValidationError(
            f"{field_name} must be a valid integer, got: {type(key_id).__name__}",
            details={"field": field_name, "provided": key_id},
        )

    if key_id_int <= 0:
        raise ValidationError(
            f"{field_name} must be a positive integer, got: {key_id_int}",
            details={"field": field_name, "provided": key_id_int},
        )

    return key_id_int


def validate_metadata_id(metadata_id: Any) -> int:
    """
    Validate and convert metadata_id to integer.

    Args:
        metadata_id: Metadata ID to validate

    Returns:
        Validated metadata ID as integer

    Raises:
        ValidationError: If metadata_id is invalid
    """
    if metadata_id is None:
        raise ValidationError(
            "Metadata ID is required.",
            details={"field": "metadata_id", "provided": None},
        )

    try:
        metadata_id_int = int(metadata_id)
    except (ValueError, TypeError):
        raise ValidationError(
            f"Metadata ID must be a valid integer, got: {type(metadata_id).__name__}",
            details={"field": "metadata_id", "provided": metadata_id},
        )

    if metadata_id_int <= 0:
        raise ValidationError(
            f"Metadata ID must be a positive integer, got: {metadata_id_int}",
            details={"field": "metadata_id", "provided": metadata_id_int},
        )

    return metadata_id_int


def validate_string_field(
    value: Any,
    field_name: str,
    max_length: Optional[int] = None,
    allow_empty: bool = False,
) -> str:
    """
    Validate a string field.

    Args:
        value: String value to validate
        field_name: Name of the field for error messages
        max_length: Maximum allowed length
        allow_empty: Whether empty strings are allowed

    Returns:
        Validated string value

    Raises:
        ValidationError: If value is invalid
    """
    if value is None:
        raise ValidationError(
            f"{field_name} is required.",
            details={"field": field_name, "provided": None},
        )

    if not isinstance(value, str):
        raise ValidationError(
            f"{field_name} must be a string, got: {type(value).__name__}",
            details={"field": field_name, "provided": value},
        )

    value_stripped = value.strip()

    if not allow_empty and not value_stripped:
        raise ValidationError(
            f"{field_name} cannot be empty.",
            details={"field": field_name, "provided": value},
        )

    if max_length is not None and len(value_stripped) > max_length:
        raise ValidationError(
            f"{field_name} must not exceed {max_length} characters, got: {len(value_stripped)}",
            details={
                "field": field_name,
                "provided_length": len(value_stripped),
                "max_length": max_length,
            },
        )

    return value_stripped

def validate_list_of_metadata_key_field(
    value: List[str]
) -> List[str]:
    """
    Validate a list of CreateMetadataKey objects and extract their names.

    Args:
        value: List of CreateMetadataKey objects to validate

    Returns:
        Validated list of metadata key names as strings

    Raises:
        ValidationError: If any value in the list is invalid
    """
    if not isinstance(value, list):
        raise ValidationError(
            "Value must be a list.",
            details={"field": "value", "provided": value},
        )

    if len(value) == 0:
        raise ValidationError(
            "List cannot be empty.",
            details={"field": "value", "provided": value},
        )

    validated_names = []
    for idx, item in enumerate(value):
        # Extract and validate the name string
        validated_name = validate_string_field(item, f"name[{idx}]", max_length=255)
        validated_names.append(validated_name)

    return validated_names


def handle_api_response(
    response: Any,
    operation: str,
    context: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Handle API response and raise appropriate errors if needed.

    Args:
        response: API response object with status and data attributes
        operation: Description of the operation (for error messages)
        context: Additional context for error messages

    Returns:
        Response data if successful

    Raises:
        ApiError: If API call failed
        NotFoundError: If resource not found
    """
    if not hasattr(response, "status"):
        raise ApiError(
            f"Invalid API response format for {operation}: response object missing 'status' attribute",
            details={"operation": operation, "response_type": type(response).__name__},
            recoverable=False,
        )

    if response.status == "success":
        return response.data

    # Extract error description
    error_description = getattr(response, "description", "Unknown error")
    if not error_description or error_description == "Unknown error":
        error_description = f"API call failed for {operation}"

    # Check if it's a "not found" error
    error_lower = error_description.lower()
    if any(
        phrase in error_lower
        for phrase in ["not found", "見つかりません", "does not exist", "not exist"]
    ):
        raise NotFoundError(
            f"{operation}: {error_description}",
            details={
                "operation": operation,
                "api_error": error_description,
                "context": context,
            },
        )

    # Generic API error
    raise ApiError(
        f"{operation}: {error_description}",
        details={
            "operation": operation,
            "api_error": error_description,
            "api_status": response.status,
            "context": context,
        },
        recoverable=True,
    )


def normalize(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return ast.literal_eval(value)
        except Exception as e:
            raise ValueError(f"Invalid list string: {value}") from e
    return value

