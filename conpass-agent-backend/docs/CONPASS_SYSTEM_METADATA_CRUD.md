# Metadata CRUD Operations API Documentation

## Overview

This document provides comprehensive details for performing CRUD (Create, Read, Update, Delete) operations on contract metadata in the ConPass system. This documentation is designed for AI agents to build external tools that interact with the metadata APIs.

## Metadata Types

The system supports two types of metadata:

1. **DEFAULT Metadata** (`type = 1`): System-defined metadata fields (e.g., contract title, company name, dates). These cannot be created or deleted by users, but their visibility can be controlled.

2. **FREE/Custom Metadata** (`type = 2`): User-defined custom metadata fields. These can be created, updated, and deleted by users within their account scope.

## Authentication

All metadata APIs require authentication via JWT token stored in HTTP cookies.

- **Cookie Name**: Set by `JWT_AUTH_COOKIE` setting (typically `auth-token`)
- **Authentication Method**: JWT token in HTTP-only cookie
- **Login Endpoint**: `POST /auth/login`
  - Request: `{"login_name": "user@example.com", "password": "password"}`
  - Response: Sets JWT cookie automatically

**Important**: All API requests must include the authentication cookie. The system automatically validates the user's account and permissions.

## Base URL

All endpoints are relative to the API base URL (e.g., `https://api.example.com/` or `/`).

---

## API Endpoints

### 1. Get Contract Metadata (READ)

**Endpoint**: `GET /contract/<contract_id>/metadata`

**Description**: Retrieves all metadata for a specific contract. Returns both DEFAULT and FREE metadata that are visible based on account and directory settings.

**URL Parameters**:

- `contract_id` (integer, required): The ID of the contract

**Request Headers**:

- Cookie: JWT authentication token

**Response Format**:

```json
{
  "response": [
    {
      "id": 123,
      "key": {
        "id": 5,
        "name": "契約書名",
        "label": "title",
        "type": 1,
        "isVisible": true
      },
      "check": false,
      "checkedBy": null,
      "value": "Sample Contract",
      "dateValue": null,
      "score": 0.95,
      "startOffset": 0,
      "endOffset": 15,
      "status": 1,
      "lock": false,
      "createdAt": "2024-01-15T10:30:00Z",
      "createdBy": {
        "id": 1,
        "loginName": "user@example.com",
        "name": "User Name"
      },
      "updatedAt": "2024-01-15T10:30:00Z",
      "updatedBy": {
        "id": 1,
        "loginName": "user@example.com",
        "name": "User Name"
      }
    }
  ]
}
```

**Response Fields**:

- `id`: Metadata record ID (null for unused FREE metadata keys)
- `key`: Metadata key information
  - `id`: MetaKey ID
  - `name`: Display name (e.g., "契約書名")
  - `label`: System label (e.g., "title", "conpass_person")
  - `type`: 1 for DEFAULT, 2 for FREE
  - `isVisible`: Whether the key is visible
- `value`: Text value (string, max 255 characters)
- `dateValue`: Date value (YYYY-MM-DD format, null if not a date field)
- `lock`: Whether the metadata is locked (locked metadata cannot be updated)
- `status`: 0 = DISABLE, 1 = ENABLE
- `check`: User verification status
- `checkedBy`: User who verified the metadata
- `score`: Confidence score (0.0-1.0) from NLP extraction
- `startOffset`/`endOffset`: Text position in source document
- `createdAt`/`updatedAt`: Timestamps
- `createdBy`/`updatedBy`: User information

**Error Responses**:

- `400 Bad Request`: Contract not found
  ```json
  "契約書が見つかりません"
  ```

**Notes**:

- Only returns metadata for keys that are visible based on account and directory settings
- Unused FREE metadata keys (not yet assigned values) are included with `id: null`
- "担当者名" (person name) metadata is automatically combined into comma-separated values

---

### 2. Create/Update Metadata (CREATE/UPDATE)

**Endpoint**: `PUT /contract/<contract_id>/metadata`

**Description**: Creates new metadata or updates existing metadata for a contract. Supports batch operations (multiple metadata items in one request).

**URL Parameters**:

- `contract_id` (integer, required): The ID of the contract

**Request Headers**:

- `Content-Type: application/json`
- Cookie: JWT authentication token

**Request Body Format**:

```json
{
  "params": {
    "list": [
      {
        "id": 123, // Optional: Include for UPDATE, omit for CREATE
        "key_id": 456, // Required for CREATE (when id is not provided)
        "value": "Some value", // Optional: Text value (string, max 255 chars)
        "dateValue": "2024-01-15", // Optional: Date value (YYYY-MM-DD format)
        "lock": false // Optional: Lock status (boolean)
      }
    ]
  }
}
```

**Request Field Rules**:

- **For UPDATE** (when `id` is provided):

  - `id` (integer, required): Existing metadata record ID
  - `key_id` (integer, optional): Cannot be specified if `id` is provided
  - `value` (string, optional): New text value (ignored if `lock: true`)
  - `dateValue` (date, optional): New date value (ignored if `lock: true`)
  - `lock` (boolean, optional): Lock/unlock the metadata

- **For CREATE** (when `id` is omitted):
  - `key_id` (integer, required): MetaKey ID to create metadata for
  - `value` (string, optional): Initial text value
  - `dateValue` (date, optional): Initial date value
  - `lock` (boolean, optional): Initial lock status

**Validation Rules**:

1. Cannot specify both `id` and `key_id` in the same request item
2. For CREATE: `key_id` must exist and be ENABLE status
3. For CREATE: `key_id` must belong to user's account or be a system-wide DEFAULT key
4. For UPDATE: `id` must exist and belong to the specified contract
5. If `lock: true`, `value` and `dateValue` updates are ignored
6. `value` is limited to 255 characters
7. `dateValue` must be in YYYY-MM-DD format

**Response Format**:
Same as GET response - returns the created/updated metadata items:

```json
{
  "response": [
    {
      "id": 123,
      "key": { ... },
      "value": "Updated value",
      "dateValue": null,
      "lock": false,
      ...
    }
  ]
}
```

**Error Responses**:

- `400 Bad Request`: Invalid parameters
  ```json
  { "msg": "パラメータが不正です" }
  ```
- `400 Bad Request`: Validation errors
  ```json
  {
    "list": [
      {
        "non_field_errors": ["Only one of `id` and `key_id` can be specified"]
      }
    ]
  }
  ```

**Special Cases**:

1. **Person Metadata** (`key.label == "conpass_person"`):

   - `value` should be comma-separated person IDs (e.g., "1,2,3")
   - System automatically creates/updates/deletes individual person metadata records
   - Example:
     ```json
     {
       "id": 123,
       "value": "1,2,3" // Creates/updates 3 person records
     }
     ```

2. **Contract Title** (`key.label == "title"`):

   - Updating title metadata automatically updates `contract.name`

3. **Locked Metadata**:
   - If `lock: true`, `value` and `dateValue` fields cannot be updated
   - Only `lock` field can be changed when metadata is locked

**Example Requests**:

**Create new FREE metadata**:

```json
{
  "params": {
    "list": [
      {
        "key_id": 10,
        "value": "Custom field value"
      }
    ]
  }
}
```

**Update existing metadata**:

```json
{
  "params": {
    "list": [
      {
        "id": 123,
        "value": "Updated value"
      }
    ]
  }
}
```

**Batch create/update**:

```json
{
  "params": {
    "list": [
      {
        "id": 123,
        "value": "Updated value 1"
      },
      {
        "key_id": 5,
        "value": "New value"
      },
      {
        "id": 124,
        "dateValue": "2024-12-31"
      },
      {
        "id": 125,
        "lock": true
      }
    ]
  }
}
```

**Update date field**:

```json
{
  "params": {
    "list": [
      {
        "id": 123,
        "dateValue": "2024-12-31"
      }
    ]
  }
}
```

---

### 3. Delete Metadata (DELETE)

**Endpoint**: `DELETE /contract/metadata/<metadata_id>`

**Description**: Soft-deletes a metadata record (sets status to DISABLE). The record is not physically removed but marked as inactive.

**URL Parameters**:

- `metadata_id` (integer, required): The ID of the metadata record to delete

**Request Headers**:

- Cookie: JWT authentication token

**Response Format**:
Empty response body with `200 OK` status on success.

**Error Responses**:

- `400 Bad Request`: Metadata not found
  ```json
  { "msg": ["メタデータが見つかりません"] }
  ```

**Notes**:

- Only ENABLE status metadata can be deleted
- Deleted metadata cannot be retrieved via GET endpoint
- This is a soft delete (status set to DISABLE, not physically removed)

**Example**:

```bash
DELETE /contract/metadata/123
```

---

## Helper Endpoints

### Get Available FREE Metadata Keys

**Endpoint**: `GET /contract/metakey/free`

**Description**: Retrieves all available FREE (custom) metadata keys for the current user's account. Useful for discovering which `key_id` values can be used when creating new metadata.

**Request Headers**:

- Cookie: JWT authentication token

**Response Format**:

```json
[
  {
    "id": 10,
    "name": "Custom Field 1",
    "label": ""
  },
  {
    "id": 11,
    "name": "Custom Field 2",
    "label": ""
  }
]
```

**Response Fields**:

- `id`: MetaKey ID (use this as `key_id` when creating metadata)
- `name`: Display name of the metadata key
- `label`: System label (usually empty for FREE keys)

**Notes**:

- Only returns FREE metadata keys (`type = 2`)
- Only returns keys for the current user's account
- Only returns ENABLE status keys

---

## Data Models

### MetaKey (Metadata Key Definition)

**Fields**:

- `id` (integer): Primary key
- `name` (string, max 255): Display name
- `label` (string, max 255): System label (e.g., "title", "conpass_person")
- `type` (integer): 1 = DEFAULT, 2 = FREE
- `account` (integer, nullable): Account ID (null for system-wide DEFAULT keys)
- `is_visible` (boolean): Visibility setting
- `status` (integer): 0 = DISABLE, 1 = ENABLE

### MetaData (Metadata Value)

**Fields**:

- `id` (integer): Primary key
- `contract` (integer): Contract ID (foreign key)
- `key` (integer): MetaKey ID (foreign key)
- `value` (string, max 255): Text value
- `date_value` (date, nullable): Date value
- `lock` (boolean): Lock status
- `status` (integer): 0 = DISABLE, 1 = ENABLE
- `check` (boolean): User verification status
- `checked_by` (integer, nullable): User ID who verified
- `score` (float): NLP extraction confidence (0.0-1.0)
- `start_offset` / `end_offset` (integer): Text position in document
- `created_at` / `updated_at` (datetime): Timestamps
- `created_by` / `updated_by` (integer): User IDs

---

## Status and Type Constants

### Status Values

- `0` = DISABLE (inactive/deleted)
- `1` = ENABLE (active)

### Type Values

- `1` = DEFAULT (system-defined metadata)
- `2` = FREE (user-defined custom metadata)

---

## Important Business Rules

1. **Account Scoping**:

   - All operations are scoped to the authenticated user's account
   - FREE metadata keys are account-specific
   - DEFAULT metadata keys are system-wide but visibility is account-specific

2. **Directory Visibility**:

   - Metadata visibility is controlled by both account-level and directory-level settings
   - GET endpoint only returns metadata for visible keys

3. **Locked Metadata**:

   - When `lock: true`, `value` and `dateValue` cannot be updated
   - Only the `lock` field itself can be changed
   - Lock status can be set during CREATE or UPDATE

4. **Person Metadata Special Handling**:

   - Person metadata (`label == "conpass_person"`) uses comma-separated values
   - System manages multiple person records automatically
   - GET endpoint combines multiple person records into comma-separated format

5. **Contract Title Auto-Update**:

   - Updating metadata with `key.label == "title"` automatically updates `contract.name`

6. **Soft Delete**:

   - DELETE operation sets `status = DISABLE`
   - Deleted metadata is not returned by GET endpoint
   - Physical deletion does not occur

7. **Batch Operations**:

   - PUT endpoint supports multiple metadata items in one request
   - Each item in the list is processed independently
   - Partial failures may occur (check response for created/updated items)

8. **Validation**:
   - `key_id` must exist and be ENABLE status
   - `key_id` must belong to user's account (or be system DEFAULT)
   - `contract_id` must exist and belong to user's account
   - Cannot specify both `id` and `key_id` in same request item

---

## Error Handling

### Common Error Scenarios

1. **Authentication Failure**:

   - Status: `401 Unauthorized`
   - Solution: Ensure JWT cookie is present and valid

2. **Contract Not Found**:

   - Status: `400 Bad Request`
   - Message: `"契約書が見つかりません"`
   - Solution: Verify `contract_id` exists and belongs to user's account

3. **Metadata Not Found**:

   - Status: `400 Bad Request`
   - Message: `{"msg": ["メタデータが見つかりません"]}`
   - Solution: Verify `metadata_id` exists and is ENABLE status

4. **Invalid Parameters**:

   - Status: `400 Bad Request`
   - Message: `{"msg": "パラメータが不正です"}`
   - Solution: Check request body format and field values

5. **Validation Errors**:

   - Status: `400 Bad Request`
   - Response: Serializer error details
   - Solution: Review validation rules and fix request data

6. **Locked Metadata Update Attempt**:
   - Status: `200 OK` (no error, but update is silently ignored)
   - Solution: Unlock metadata first, then update

---

## Complete Workflow Examples

### Example 1: Create Custom Metadata for a Contract

```bash
# Step 1: Get available FREE metadata keys
GET /contract/metakey/free
# Response: [{"id": 10, "name": "Custom Field", "label": ""}]

# Step 2: Create metadata using key_id
PUT /contract/123/metadata
{
  "params": {
    "list": [
      {
        "key_id": 10,
        "value": "My custom value"
      }
    ]
  }
}
```

### Example 2: Update Multiple Metadata Fields

```bash
# Step 1: Get current metadata
GET /contract/123/metadata
# Response includes metadata with IDs

# Step 2: Update multiple fields
PUT /contract/123/metadata
{
  "params": {
    "list": [
      {
        "id": 100,
        "value": "Updated text"
      },
      {
        "id": 101,
        "dateValue": "2024-12-31"
      },
      {
        "id": 102,
        "lock": true
      }
    ]
  }
}
```

### Example 3: Delete Metadata

```bash
# Step 1: Get metadata to find ID
GET /contract/123/metadata
# Response includes metadata with IDs

# Step 2: Delete metadata
DELETE /contract/metadata/100
```

### Example 4: Handle Person Metadata

```bash
# Update person metadata (comma-separated person IDs)
PUT /contract/123/metadata
{
  "params": {
    "list": [
      {
        "id": 200,  // Person metadata ID
        "value": "1,2,3"  // Three person IDs
      }
    ]
  }
}
# System automatically manages individual person records
```

---

## Testing Checklist for AI Agents

When building tools, ensure:

1. ✅ Authentication cookie is included in all requests
2. ✅ Contract ID exists and belongs to user's account
3. ✅ For CREATE: `key_id` is valid and belongs to account
4. ✅ For UPDATE: `id` exists and belongs to contract
5. ✅ Cannot specify both `id` and `key_id` in same item
6. ✅ Locked metadata cannot have `value`/`dateValue` updated
7. ✅ Date values are in YYYY-MM-DD format
8. ✅ Text values are max 255 characters
9. ✅ Handle batch operations correctly
10. ✅ Handle person metadata comma-separated format
11. ✅ Handle soft delete (status = DISABLE)
12. ✅ Error responses are properly handled

---

## Additional Notes

- All timestamps are in UTC
- Date values use YYYY-MM-DD format
- Text values are limited to 255 characters
- The system uses soft deletes (status-based, not physical deletion)
- Metadata keys can be account-specific (FREE) or system-wide (DEFAULT)
- Visibility is controlled at both account and directory levels
- Person metadata requires special handling with comma-separated values

---

## Endpoint Summary

| Method | Endpoint                           | Description                              |
| ------ | ---------------------------------- | ---------------------------------------- |
| GET    | `/contract/<contract_id>/metadata` | Get all metadata for a contract          |
| PUT    | `/contract/<contract_id>/metadata` | Create/Update metadata (batch supported) |
| DELETE | `/contract/metadata/<metadata_id>` | Delete metadata (soft delete)            |
| GET    | `/contract/metakey/free`           | Get available FREE metadata keys         |

---

**Last Updated**: Based on codebase analysis
**Version**: 1.0
