# Metadata Update API - Complete Agent Implementation Guide

## Overview

This document provides comprehensive technical details for implementing an AI agent that can update contract metadata using the ConPass backend APIs. This guide is designed to be used as context for LLM-based agents.

## Authentication

### Requirements

- **Method**: JWT token stored in HTTP-only cookie
- **Cookie Name**: Set by `JWT_AUTH_COOKIE` setting (typically `auth-token`)
- **Login Endpoint**: `POST /auth/login`
- **Login Request Body**:
  ```json
  {
    "login_name": "user@example.com",
    "password": "password"
  }
  ```
- **Login Response**: Automatically sets JWT cookie in response headers
- **All Subsequent Requests**: Must include the authentication cookie

### Important Notes

- The system automatically validates the user's account and permissions
- All operations are scoped to the authenticated user's account
- Authentication failures return `401 Unauthorized`

---

## Update Metadata Endpoint

### Endpoint Details

- **URL**: `PUT /contract/<contract_id>/metadata`
- **Method**: `PUT`
- **URL Parameter**: `contract_id` (integer, required) - The ID of the contract
- **Content-Type**: `application/json`

### Request Structure

```json
{
  "params": {
    "list": [
      {
        "id": 123,
        "value": "Updated value",
        "dateValue": "2024-12-31",
        "lock": false
      }
    ]
  }
}
```

### Request Fields

The API supports two types of operations in the same request:

#### 1. UPDATE Operation (For Existing Metadata)

Use when the metadata field already has a value (`id` is not null).

| Field       | Type    | Required             | Description                 | Constraints                                          |
| ----------- | ------- | -------------------- | --------------------------- | ---------------------------------------------------- |
| `id`        | integer | **Yes** (for UPDATE) | Existing metadata record ID | Must exist, belong to contract, and be ENABLE status |
| `value`     | string  | No                   | New text value              | Max 255 characters. Ignored if `lock: true`          |
| `dateValue` | date    | No                   | New date value              | Format: `YYYY-MM-DD`. Ignored if `lock: true`        |
| `lock`      | boolean | No                   | Lock/unlock status          | Can be changed even when metadata is locked          |

#### 2. CREATE Operation (For Empty Metadata Fields)

Use when the metadata field has no value yet (`id` is null in GET response).

| Field       | Type    | Required             | Description                       | Constraints                      |
| ----------- | ------- | -------------------- | --------------------------------- | -------------------------------- |
| `key_id`    | integer | **Yes** (for CREATE) | MetaKey ID from `key.id`          | Must exist and be ENABLE status  |
| `value`     | string  | No                   | Initial text value                | Max 255 characters               |
| `dateValue` | date    | No                   | Initial date value                | Format: `YYYY-MM-DD`             |
| `lock`      | boolean | No                   | Initial lock status (rarely used) | Usually omitted for new metadata |

**Important**: Cannot specify both `id` and `key_id` in the same list item. Each item must be either an UPDATE (with `id`) or CREATE (with `key_id`).

### Validation Rules (Enforced by Serializer)

1. **Mutual Exclusivity**: Cannot specify both `id` and `key_id` in the same request item

   - Error: `{"non_field_errors": ["Only one of `id`and`key_id` can be specified"]}`
   - Status: `400 Bad Request`

2. **Metadata Existence** (for UPDATE):

   - `id` must exist in database
   - `id` must belong to the specified `contract_id`
   - Metadata must have `status = ENABLE` (status = 1)
   - Error: `{"msg": "パラメータが不正です"}` (Invalid parameters)
   - Status: `400 Bad Request`

3. **Lock Status Behavior**:

   - If `metadata.lock == true`:
     - `value` updates are **silently ignored** (no error, but value doesn't change)
     - `dateValue` updates are **silently ignored** (no error, but date doesn't change)
     - Only `lock` field can be changed (to unlock: `{"id": 123, "lock": false}`)

4. **Field Length Constraints**:

   - `value`: Maximum 255 characters
   - `dateValue`: Must be valid date in `YYYY-MM-DD` format

5. **Account Scoping**:
   - Contract must belong to authenticated user's account
   - Metadata must belong to the contract

### Implementation Logic (From Source Code)

The update process follows this logic:

```python
# Pseudocode from actual implementation
def _update_metadata(req_data, contract_id, now):
    # 1. Fetch metadata - must exist and be ENABLE
    metadata = MetaData.objects.filter(
        pk=req_data.get('id'),
        contract_id=contract_id,
        status=MetaData.Status.ENABLE.value  # status = 1
    ).get()

    # 2. Special handling for person metadata
    if metadata.key.label == 'conpass_person':
        if 'value' in req_data and not metadata.lock:
            # Update person metadata (comma-separated IDs)
            _update_person_metadata(req_data, contract_id, now)
        if 'lock' in req_data:
            metadata.lock = req_data['lock']
            metadata.save()
    else:
        # 3. Regular metadata update
        if 'value' in req_data and not metadata.lock:
            metadata.value = req_data['value']
        if 'dateValue' in req_data and not metadata.lock:
            metadata.date_value = req_data['dateValue']
        if 'lock' in req_data:
            metadata.lock = req_data['lock']

        # 4. Update audit fields
        metadata.updated_by = request.user
        metadata.updated_at = now
        metadata.save()

    return metadata
```

### Special Cases

#### 1. Person Metadata (`key.label == "conpass_person"`)

**Behavior**:

- `value` must be comma-separated person IDs (e.g., `"1,2,3"`)
- System automatically manages multiple person records:
  - **Adds**: Person IDs in new value but not in existing records
  - **Deletes**: Person IDs in existing records but not in new value
  - **Updates**: Person IDs present in both (updates timestamp)
- Each person ID becomes a separate `MetaData` record with the same `key`

**Example Request**:

```json
{
  "params": {
    "list": [
      {
        "id": 200,
        "value": "1,2,3"
      }
    ]
  }
}
```

**What Happens**:

- If existing persons are `[1, 4]`:
  - Person `1` is updated (timestamp refreshed)
  - Person `2` is created (new record)
  - Person `3` is created (new record)
  - Person `4` is deleted (removed from contract)

**Important**: Person metadata updates are ignored if `lock: true`, just like regular metadata.

#### 2. Contract Title (`key.label == "title"`)

**Behavior**:

- Updating title metadata **automatically updates** `contract.name`
- This happens after metadata update completes
- Both operations use the same timestamp

**Example Request**:

```json
{
  "params": {
    "list": [
      {
        "id": 100,
        "value": "New Contract Title"
      }
    ]
  }
}
```

**What Happens**:

1. Metadata record with `id=100` is updated with new value
2. `Contract.name` is automatically set to "New Contract Title"
3. `Contract.updated_at` and `Contract.updated_by` are updated

#### 3. Locked Metadata

**Behavior**:

- When `metadata.lock == true`:
  - `value` field in request is **ignored** (no error, silent skip)
  - `dateValue` field in request is **ignored** (no error, silent skip)
  - `lock` field can still be changed (to unlock)
- To update locked metadata:
  1. First unlock: `{"id": 123, "lock": false}`
  2. Then update: `{"id": 123, "value": "New value"}`

**Example - Unlocking and Updating**:

```json
// Step 1: Unlock
{
  "params": {
    "list": [
      {"id": 123, "lock": false}
    ]
  }
}

// Step 2: Update value
{
  "params": {
    "list": [
      {"id": 123, "value": "New value"}
    ]
  }
}
```

### Batch Operations

**Supported**: Yes - Multiple metadata items can be updated in a single request.

**Behavior**:

- Each item in `list` is processed independently
- If one item fails validation, the entire request fails (returns 400)
- All successful updates are returned in response
- Processing order: Sequential (one after another)

**Example - Batch Update**:

```json
{
  "params": {
    "list": [
      {
        "id": 100,
        "value": "Updated text field"
      },
      {
        "id": 101,
        "dateValue": "2024-12-31"
      },
      {
        "id": 102,
        "lock": true
      },
      {
        "id": 103,
        "value": "Another update",
        "lock": false
      }
    ]
  }
}
```

**Response**: Returns all updated metadata items in the response array.

### Mixed UPDATE and CREATE Operations

You can combine UPDATE and CREATE operations in a single batch request.

**Example - Mixed Batch (UPDATE + CREATE)**:

```json
{
  "params": {
    "list": [
      {
        "id": 90429,
        "value": "Updated Company A"
      },
      {
        "id": 90430,
        "value": "Updated Company B"
      },
      {
        "key_id": 4,
        "value": "New Company C"
      },
      {
        "key_id": 5,
        "value": "New Company D"
      }
    ]
  }
}
```

**Explanation**:

- Items with `id` (90429, 90430) are UPDATE operations for existing metadata
- Items with `key_id` (4, 5) are CREATE operations for empty metadata fields
- All operations are processed in a single request
- Response will include all created and updated metadata with their IDs

**When to Use CREATE (key_id)**:

- The metadata field exists in the contract template
- But it has no value yet (`id: null` in GET response)
- You want to set its first value

**When to Use UPDATE (id)**:

- The metadata field already has a value (`id: 12345` in GET response)
- You want to change or update that value

---

## Response Format

### Success Response: `200 OK`

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
      "value": "Updated value",
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
      "updatedAt": "2024-01-15T11:45:00Z",
      "updatedBy": {
        "id": 1,
        "loginName": "user@example.com",
        "name": "User Name"
      }
    }
  ]
}
```

### Response Fields

| Field           | Type         | Description                                    |
| --------------- | ------------ | ---------------------------------------------- |
| `id`            | integer      | Metadata record ID                             |
| `key`           | object       | Metadata key information                       |
| `key.id`        | integer      | MetaKey ID                                     |
| `key.name`      | string       | Display name (e.g., "契約書名")                |
| `key.label`     | string       | System label (e.g., "title", "conpass_person") |
| `key.type`      | integer      | 1 = DEFAULT, 2 = FREE                          |
| `key.isVisible` | boolean      | Visibility setting                             |
| `value`         | string       | Text value (null if empty)                     |
| `dateValue`     | date         | Date value (null if not a date field)          |
| `lock`          | boolean      | Lock status                                    |
| `status`        | integer      | 0 = DISABLE, 1 = ENABLE                        |
| `check`         | boolean      | User verification status                       |
| `checkedBy`     | object\|null | User who verified (null if not checked)        |
| `score`         | float        | NLP extraction confidence (0.0-1.0)            |
| `startOffset`   | integer      | Text start position in document                |
| `endOffset`     | integer      | Text end position in document                  |
| `createdAt`     | datetime     | Creation timestamp (ISO 8601)                  |
| `createdBy`     | object       | User who created                               |
| `updatedAt`     | datetime     | Last update timestamp (ISO 8601)               |
| `updatedBy`     | object       | User who last updated                          |

---

## Error Responses

### 1. Validation Error: `400 Bad Request`

**When**: Serializer validation fails (e.g., both `id` and `key_id` specified)

```json
{
  "list": [
    {
      "non_field_errors": ["Only one of `id` and `key_id` can be specified"]
    }
  ]
}
```

### 2. Invalid Parameters: `400 Bad Request`

**When**: Metadata not found, contract not found, or invalid ID

```json
{
  "msg": "パラメータが不正です"
}
```

**Common Causes**:

- Metadata ID doesn't exist
- Metadata belongs to different contract
- Metadata has `status = DISABLE` (soft-deleted)
- Contract doesn't belong to user's account

### 3. Authentication Error: `401 Unauthorized`

**When**: JWT token missing, invalid, or expired

**Response**: Standard Django REST Framework authentication error

---

## Complete Workflow for AI Agent

### Step 1: Authenticate User

```http
POST /auth/login
Content-Type: application/json

{
  "login_name": "user@example.com",
  "password": "password"
}
```

**Action**: Store the authentication cookie from response headers.

### Step 2: Get Current Metadata (Optional but Recommended)

```http
GET /contract/123/metadata
Cookie: auth-token=<jwt_token>
```

**Purpose**:

- Verify contract exists
- Get metadata IDs for updates
- Check current `lock` status
- Verify metadata belongs to contract

**Response**: Array of metadata objects with their IDs.

### Step 3: Prepare Update Request

**Check Before Updating**:

1. ✅ Metadata ID exists in GET response
2. ✅ Metadata `lock` status (if `true`, must unlock first)
3. ✅ Contract belongs to user's account
4. ✅ `value` length ≤ 255 characters
5. ✅ `dateValue` format is `YYYY-MM-DD`

**For Person Metadata**:

- Convert person list to comma-separated string: `"1,2,3"`

**For Locked Metadata**:

- If locked and need to update value:
  - First request: `{"id": 123, "lock": false}`
  - Second request: `{"id": 123, "value": "New value"}`

### Step 4: Execute Update Request

```http
PUT /contract/123/metadata
Content-Type: application/json
Cookie: auth-token=<jwt_token>

{
  "params": {
    "list": [
      {
        "id": 456,
        "value": "Updated value"
      }
    ]
  }
}
```

### Step 5: Handle Response

**Success (`200 OK`)**:

- Parse response to verify updates
- Check `updatedAt` timestamp to confirm changes
- For title metadata, verify `contract.name` was also updated

**Error (`400 Bad Request`)**:

- Check error message:
  - `"パラメータが不正です"` → Metadata not found or invalid
  - `"Only one of id and key_id can be specified"` → Validation error
- Retry with corrected data

**Error (`401 Unauthorized`)**:

- Re-authenticate and retry request

---

## Example Scenarios

### Scenario 1: Simple Text Update

**Goal**: Update a metadata field's text value

**Request**:

```json
{
  "params": {
    "list": [
      {
        "id": 456,
        "value": "New text value"
      }
    ]
  }
}
```

**Expected Response**: `200 OK` with updated metadata object.

### Scenario 2: Update Date Field

**Goal**: Update a date metadata field

**Request**:

```json
{
  "params": {
    "list": [
      {
        "id": 457,
        "dateValue": "2024-12-31"
      }
    ]
  }
}
```

**Expected Response**: `200 OK` with updated metadata object showing new `dateValue`.

### Scenario 3: Update Multiple Fields

**Goal**: Update several metadata fields in one request

**Request**:

```json
{
  "params": {
    "list": [
      {
        "id": 100,
        "value": "Updated field 1"
      },
      {
        "id": 101,
        "value": "Updated field 2"
      },
      {
        "id": 102,
        "dateValue": "2024-12-31"
      }
    ]
  }
}
```

**Expected Response**: `200 OK` with array of 3 updated metadata objects.

### Scenario 4: Lock Metadata

**Goal**: Lock a metadata field to prevent editing

**Request**:

```json
{
  "params": {
    "list": [
      {
        "id": 200,
        "lock": true
      }
    ]
  }
}
```

**Expected Response**: `200 OK` with metadata object showing `lock: true`.

### Scenario 5: Update Locked Metadata

**Goal**: Update a locked metadata field

**Step 1 - Unlock**:

```json
{
  "params": {
    "list": [
      {
        "id": 200,
        "lock": false
      }
    ]
  }
}
```

**Step 2 - Update**:

```json
{
  "params": {
    "list": [
      {
        "id": 200,
        "value": "New value after unlock"
      }
    ]
  }
}
```

**Expected Response**: Both requests return `200 OK`.

### Scenario 6: Update Person Metadata

**Goal**: Update assigned persons for a contract

**Current State**: Persons `[1, 4]` assigned

**Request**:

```json
{
  "params": {
    "list": [
      {
        "id": 300,
        "value": "1,2,3"
      }
    ]
  }
}
```

**What Happens**:

- Person `1`: Updated (timestamp refreshed)
- Person `2`: Created (new assignment)
- Person `3`: Created (new assignment)
- Person `4`: Deleted (removed from contract)

**Expected Response**: `200 OK` with person metadata object.

### Scenario 7: Update Contract Title

**Goal**: Update contract title (which also updates contract name)

**Request**:

```json
{
  "params": {
    "list": [
      {
        "id": 500,
        "value": "New Contract Title"
      }
    ]
  }
}
```

**What Happens**:

1. Metadata record `id=500` is updated
2. `Contract.name` is automatically set to "New Contract Title"
3. `Contract.updated_at` and `Contract.updated_by` are updated

**Expected Response**: `200 OK` with updated metadata object.

---

## Error Handling Strategies

### Strategy 1: Validate Before Update

**Before sending update request**:

1. Call `GET /contract/<contract_id>/metadata`
2. Verify metadata ID exists in response
3. Check `lock` status
4. Validate field constraints (length, format)
5. Then send update request

**Benefits**: Reduces failed requests, better user experience.

### Strategy 2: Handle Locked Metadata

**If metadata is locked**:

1. Check `lock: true` in GET response
2. If update needed:
   - First: Unlock (`{"id": X, "lock": false}`)
   - Then: Update value
3. Optionally: Re-lock after update

**Code Pattern**:

```python
if metadata['lock'] == True and needs_value_update:
    # Step 1: Unlock
    unlock_request = {"id": metadata_id, "lock": false}
    # Step 2: Update
    update_request = {"id": metadata_id, "value": new_value}
```

### Strategy 3: Retry with Error Correction

**On `400 Bad Request` with `"パラメータが不正です"`**:

1. Re-fetch metadata list
2. Verify metadata ID still exists
3. Check if metadata was soft-deleted (`status = DISABLE`)
4. Retry with valid ID or report error

### Strategy 4: Batch Error Handling

**For batch updates**:

- If one item fails, entire request fails
- Strategy: Update items individually if batch fails
- Or: Validate all items before sending batch request

---

## Important Implementation Notes

### 1. Silent Failures (Locked Metadata)

**Critical**: When `lock: true`, `value` and `dateValue` updates are **silently ignored**. The API returns `200 OK` but the value doesn't change.

**Detection**:

- Compare `value` in response with requested value
- Check `updatedAt` timestamp (won't change if update was ignored)
- Always check `lock` status before updating

### 2. Person Metadata Complexity

**Important**: Person metadata uses comma-separated values but creates multiple database records. The GET endpoint combines them back into comma-separated format.

**When Updating**:

- Provide full list of person IDs (not just additions)
- System calculates diff and adds/removes/updates accordingly
- Example: If current is `"1,2"` and you want `"2,3"`:
  - Send: `{"id": X, "value": "2,3"}`
  - System removes `1`, keeps `2`, adds `3`

### 3. Contract Title Side Effect

**Automatic Update**: Updating title metadata (`key.label == "title"`) automatically updates `contract.name`. This is a side effect that happens automatically.

**No Separate API Call Needed**: Don't call contract update API separately.

### 4. Timestamp Updates

**Automatic**: `updatedAt` and `updatedBy` are automatically set by the system. Don't include these in request.

### 5. Account Scoping

**All Operations**: Automatically scoped to authenticated user's account. You cannot update metadata for contracts in other accounts.

**Verification**: System checks `contract.account == request.user.account` before allowing updates.

---

## Testing Checklist for AI Agent

When implementing the agent, ensure it handles:

- [ ] Authentication cookie management
- [ ] Contract existence verification
- [ ] Metadata ID validation
- [ ] Lock status checking
- [ ] Locked metadata unlock workflow
- [ ] Value length validation (≤ 255 chars)
- [ ] Date format validation (YYYY-MM-DD)
- [ ] Person metadata comma-separated format
- [ ] Batch update operations
- [ ] Error response parsing
- [ ] Silent failure detection (locked metadata)
- [ ] Contract title side effect handling
- [ ] Account scoping verification
- [ ] Soft-deleted metadata handling (status = DISABLE)

---

## Summary

### Key Takeaways for AI Agent Implementation

1. **Always authenticate first** - JWT cookie required for all requests
2. **Check lock status** - Locked metadata silently ignores value updates
3. **Validate before update** - Get metadata list first to verify IDs exist
4. **Handle person metadata specially** - Use comma-separated person IDs
5. **Account scoping is automatic** - Cannot access other accounts' data
6. **Batch operations supported** - Multiple updates in one request
7. **Title updates are special** - Automatically updates contract.name
8. **Error handling is critical** - Check for 400/401 errors and handle appropriately
9. **Silent failures possible** - Verify updates by checking response values
10. **Soft deletes exist** - Only ENABLE status metadata can be updated

### Endpoint Summary

| Method | Endpoint                           | Purpose                         |
| ------ | ---------------------------------- | ------------------------------- |
| POST   | `/auth/login`                      | Authenticate and get JWT cookie |
| GET    | `/contract/<contract_id>/metadata` | Get all metadata for contract   |
| PUT    | `/contract/<contract_id>/metadata` | Create/Update metadata (batch)  |
| DELETE | `/contract/metadata/<metadata_id>` | Soft-delete metadata            |

---

**Last Updated**: Based on codebase analysis of `app/conpass/views/contract/views.py` and `app/conpass/views/contract/serializer/contract_item_serializer.py`
**Version**: 1.0
