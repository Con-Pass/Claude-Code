"""
Schemas for metadata CRUD operations with approval workflow.

These schemas define the action templates that agents return (for user approval)
and the execution requests that APIs process (after user approval).
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator

# --- Metadata Update Item Schema (Contract Level) ---
class MetadataUpdateItem(BaseModel):
    """
    Input model for updating a single metadata item.

    Used by the update_metadata tool to define the structure of each update.
    The LLM uses this schema to construct update requests.

    Supports both UPDATE (existing metadata with metadata_id) and CREATE (new metadata with key_id) operations.
    """

    metadata_id: Optional[int] = Field(
        None,
        description=(
            "The ID of the metadata record to update. "
            "Get this from read_metadata tool response. Must exist and be in ENABLE status. "
            "Use this for updating existing metadata (when id is not null). "
            "For creating new metadata (when id is null), use key_id instead."
        ),
    )
    key_id: Optional[int] = Field(
        None,
        description=(
            "The ID of the metadata key (key.id from read_metadata response). "
            "Use this when the metadata has no value yet (id is null) to create a new metadata record. "
            "Do not use together with metadata_id."
        ),
    )
    value: Optional[str] = Field(
        None,
        max_length=255,
        description=(
            "New text value (max 255 characters). "
            "For person metadata (key.label == 'conpass_person'), use comma-separated person IDs: '1,2,3'"
        ),
    )
    date_value: Optional[str] = Field(
        None,
        description="New date value in YYYY-MM-DD format (e.g., '2024-12-31')",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    lock: Optional[bool] = Field(
        None, description="New lock status (True to lock, False to unlock)"
    )

    @field_validator("value")
    @classmethod
    def validate_value_length(cls, v):
        if v is not None and len(v) > 255:
            raise ValueError("Value must not exceed 255 characters")
        return v

    @field_validator("key_id")
    @classmethod
    def validate_mutually_exclusive_ids(cls, v, info):
        """Ensure metadata_id and key_id are not both provided."""
        if v is not None and info.data.get("metadata_id") is not None:
            raise ValueError(
                "Cannot provide both metadata_id and key_id. Use metadata_id for updates, key_id for creates."
            )
        if v is None and info.data.get("metadata_id") is None:
            raise ValueError(
                "Either metadata_id (for update) or key_id (for create) must be provided."
            )
        return v

class MetadataUpdateItemV2(BaseModel):
    metadata_id: Optional[int] = Field(None)
    key_id: Optional[int] = Field(None)
    value: Optional[str] = Field(..., max_length=255)
    previous_value: Optional[str] = Field(None)
    date_value: Optional[str] = Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    lock: Optional[bool] = Field(None)


    @model_validator(mode="after")
    def enforce_create_vs_update(self):
        is_create = not self.previous_value  # None or empty string
        is_update = bool(self.previous_value)

        if is_create:
            # CREATE flow
            self.metadata_id = None
            if self.key_id is None:
                raise ValueError(
                    "key_id is required when previous_value is empty (Create operation)"
                )

        if is_update:
            # UPDATE flow
            self.key_id = None
            if self.metadata_id is None:
                raise ValueError(
                    "metadata_id is required when previous_value is provided (UPDATE operation)"
                )

        return self

class MetadataItem(BaseModel):
    """
    Unified metadata item structure for all CRUD operations (CREATE/UPDATE/DELETE).

    This structure provides comprehensive information for frontend rendering:
    - All identifiers (metadata_id, key_id)
    - All new/updated values (value, date_value, lock)
    - All current/existing values (current_value, current_date_value, current_lock)
    - All display information (key_name, key_label)
    """

    # Identifiers
    metadata_id: Optional[int] = Field(
        None, description="Metadata record ID (required for UPDATE/DELETE operations)"
    )
    key_id: Optional[int] = Field(
        None, description="MetaKey ID (required for CREATE operations)"
    )

    # New/Updated values (what will be set)
    value: Optional[str] = Field(
        None,
        max_length=255,
        description="New or updated text value (max 255 characters)",
    )
    date_value: Optional[str] = Field(
        None,
        description="New or updated date value in YYYY-MM-DD format",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    lock: Optional[bool] = Field(None, description="New or updated lock status")

    # Current/Existing values (what exists now, for display/comparison)
    current_value: Optional[str] = Field(
        None,
        description="Current text value (for UPDATE/DELETE operations, or display)",
    )
    current_date_value: Optional[str] = Field(
        None,
        description="Current date value (for UPDATE/DELETE operations, or display)",
    )
    current_lock: Optional[bool] = Field(
        None,
        description="Current lock status (for UPDATE/DELETE operations, or display)",
    )

    # Display information for frontend
    key_name: Optional[str] = Field(
        None, description="Human-readable metadata key name (for display)"
    )
    key_label: Optional[str] = Field(
        None, description="Metadata key label (for display)"
    )

    @field_validator("value")
    @classmethod
    def validate_value_length(cls, v):
        if v is not None and len(v) > 255:
            raise ValueError("Value must not exceed 255 characters")
        return v


class UpdateMetadataAction(BaseModel):
    """Action template for UPDATE metadata operations."""

    action_type: Literal["update"] = "update"
    contract_id: int = Field(..., description="Target contract ID")
    metadata_items: List[MetadataItem] = Field(
        ..., description="Metadata items to update"
    )
    title: str = Field(..., description="Title of the action being performed")
    confirmation_api_url: str = Field(
        ..., description="API URL to call when user confirms the action"
    )
    cancel_api_url: str = Field(
        ..., description="API URL to call when user cancels the action"
    )
    status: Literal["pending", "confirmed", "cancelled"] = Field(
        default="pending",
        description="Status of the action (pending, confirmed, or cancelled)",
    )
    error_message: Optional[str] = Field(
        None, description="Error message if validation or execution failed"
    ),
    jwt_token: Optional[str] = Field(
        None, description="JWT token of hashed metadata action"
    )

    @field_validator("metadata_items")
    @classmethod
    def validate_update_items(cls, v):
        if not v:
            raise ValueError("At least one metadata item is required")
        for item in v:
            # Either metadata_id (UPDATE) or key_id (CREATE) must be present
            if item.metadata_id is None and item.key_id is None:
                raise ValueError(
                    "Either metadata_id (for UPDATE) or key_id (for CREATE) is required"
                )
        return v

# --- Metadata Key Action Request Payload Schema (API Level) ---
class MetadataKeyActionRequest(BaseModel):
    jwt_token: str

# --- Metadata Create/Delete Tool Param Schema ---
class CreateMetadataKey(BaseModel):

    name: str = Field(
        ..., description="Display name for the new metadata key"
    )
class DeleteMetadataKey(BaseModel):
    key_id: int = Field(..., description="ID of the metadata key to delete")
    key_name: str = Field(
        ..., max_length=255, description="Name of the metadata key to delete"
    )

# --- Base Metadata Action Schema ---
class BaseMetadataAction(BaseModel):
    title: Optional[str] = Field(
        None, description="Title of the action being performed")
    confirmation_api_url: Optional[str] = Field(
        None, description="API URL to call when user confirms the action"
    )
    cancel_api_url: Optional[str] = Field(
        None, description="API URL to call when user cancels the action"
    )
    status: Optional[Literal["pending", "confirmed", "cancelled"]] = Field(
        default="pending",
        description="Status of the action (pending, confirmed, or cancelled)",
    )
    is_error: Optional[bool] = Field(
        False, description="Flag indicating if the action represents an error state")
    error_code: Optional[str] = Field(
        None, description="Error code if validation or execution failed")
    error_message: Optional[str] = Field(
        None, description="Error message if validation or execution failed"
    )
    jwt_token: Optional[str] = Field(
        None, description="JWT token of hashed metadata action"
    )

# --- Metadata Create/Update/Delete Action Schema (Global Level) ---
class CreateMetadataKeyAction(BaseMetadataAction):
    """Action template for CREATE metadata key operations."""

    action_type: Literal["create_key"] = "create_key"
    names: List[CreateMetadataKey] = Field(
        ..., description="Display names for new metadata keys"
    )


    @field_validator("names")
    @classmethod
    def validate_names(cls, v: List[CreateMetadataKey]):
        if not v:
            raise ValueError("At least one metadata key name is required")
        for item in v:
            if not isinstance(item, CreateMetadataKey):
                raise ValueError(f"Each item must be a CreateMetadataKey object, got {type(item).__name__}")
            if not item.name or not item.name.strip():
                raise ValueError("Metadata key name cannot be empty")
            if len(item.name.strip()) > 255:
                raise ValueError("Metadata key name must not exceed 255 characters")
        return v
class DeleteMetadataKeyAction(BaseMetadataAction):
    """Action template for DELETE metadata key operation"""

    action_type: Literal["delete_key"] = "delete_key"
    keys: List[DeleteMetadataKey] = Field(
        ..., description="Metadata keys to delete"
    )

    @field_validator("keys")
    @classmethod
    def validate_keys(cls, v: List[DeleteMetadataKey]):
        if not v:
            raise ValueError("At least one metadata key info (name, id) is required")

        for item in v:
            if not item.key_id:
                raise ValueError("Metadata key ID cannot be empty")

            if not item.key_name or not item.key_name.strip():
                raise ValueError("Metadata key name cannot be empty")

            if len(item.key_name.strip()) > 255:
                raise ValueError("Metadata key name must not exceed 255 characters")

        return v
class UpdateMetadataKeyAction(BaseModel):
    """Action template for UPDATE metadata key operations."""

    action_type: Literal["update_key"] = "update_key"
    key_id: Optional[int] = Field(
        None,
        description="ID of the metadata key to update (populated during validation)",
    )
    current_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Current name of the metadata key (for display)",
    )
    name: str = Field(
        ..., max_length=255, description="New display name for the metadata key"
    )
    title: str = Field(..., description="Title of the action being performed")
    confirmation_api_url: str = Field(
        ..., description="API URL to call when user confirms the action"
    )
    cancel_api_url: str = Field(
        ..., description="API URL to call when user cancels the action"
    )
    status: Literal["pending", "confirmed", "cancelled"] = Field(
        default="pending",
        description="Status of the action (pending, confirmed, or cancelled)",
    )
    error_message: Optional[str] = Field(
        None, description="Error message if validation or execution failed"
    )
    jwt_token: Optional[str] = Field(
        None, description="JWT token of hashed metadata action"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Metadata key name cannot be empty")
        if len(v) > 255:
            raise ValueError("Metadata key name must not exceed 255 characters")
        return v

# --- Metadata Key Visibility Update (Directory Level) ---
class DirectoryMetadataKeyUpdate(BaseModel):
    """Model for updating a single metadata key's visibility in a directory."""

    key_id: int = Field(..., description="MetaKey ID to update")
    key_name: Optional[str] = Field(
        None, description="Display name of the metadata key (for frontend display)"
    )
    key_type: Literal["DEFAULT", "FREE"] = Field(
        ..., description="Metadata key type: DEFAULT (system) or FREE (custom)"
    )
    is_visible: bool = Field(
        ..., description="New visibility setting for this directory"
    )
    meta_key_directory_id: Optional[int] = Field(
        None,
        description="Existing MetaKeyDirectory ID if updating an existing association, None if creating new",
    )
class DirectoryMetadataKey(BaseModel):
    key_id: int = Field(..., description="MetaKey ID")
    key_type: Literal["DEFAULT", "FREE"] = Field(
        ..., description="Metadata key type: DEFAULT (system) or FREE (custom)"
    )
    is_visible: bool = Field(..., description="Current visibility setting")
class UpdateDirectoryMetadataVisibilityAction(BaseModel):
    """Action template for updating directory metadata visibility operations."""

    action_type: Literal["update_directory_visibility"] = "update_directory_visibility"
    directory_id: int = Field(..., description="Directory ID to update")
    directory_name: Optional[str] = Field(
        None, description="Directory name for display purposes"
    )
    metadata_key_updates: List[DirectoryMetadataKeyUpdate] = Field(
        ..., description="List of metadata key visibility updates"
    )
    title: str = Field(..., description="Title of the action being performed")
    confirmation_api_url: str = Field(
        ..., description="API URL to call when user confirms the action"
    )
    cancel_api_url: str = Field(
        ..., description="API URL to call when user cancels the action"
    )
    status: Literal["pending", "confirmed", "cancelled"] = Field(
        default="pending",
        description="Status of the action (pending, confirmed, or cancelled)",
    )
    error_message: Optional[str] = Field(
        None, description="Error message if validation or execution failed"
    )
    jwt_token: Optional[str] = Field(
        None, description="JWT token of hashed metadata action"
    )
    @model_validator(mode="after")
    def validate_updates(self):
        # Allow empty list if error_message is provided (for error cases)
        if not self.metadata_key_updates and self.error_message is None:
            raise ValueError("At least one metadata key update is required")
        return self

# --- Metadata Execution Response Schema---
class MetadataExecutionResponse(BaseModel):
    """Response from metadata execution APIs."""

    status: Literal["success", "error"] = Field(..., description="Execution status")
    message: str = Field(..., description="Human-readable result message")
    data: Optional[Dict[str, Any]] = Field(
        None, description="Response data from ConPass API"
    )
    error_details: Optional[str] = Field(
        None, description="Detailed error information if status is error"
    )

# --- Metadata Action Error Response Schema ---
class MetadataActionError(BaseModel):
    """Error response template for metadata actions."""

    is_error: Optional[bool] = False
    error_code: Optional[str] = Field(None, description="Standardized error code")
    error_message: Optional[str] = Field(None, description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error context"
    )
