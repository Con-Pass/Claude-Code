# Guide: Adding Custom Metadata to Contracts

This document provides a comprehensive, step-by-step guide for adding custom (FREE) metadata fields to contracts in the ConPass system. This guide is designed to be used by AI agents to automate the process of creating and managing custom metadata.

## Overview

Adding custom metadata to a contract requires **four distinct steps**:

1. **Create a FREE MetaKey** - Define the metadata field at the account level
2. **Configure Directory Settings** - Enable the metadata field for specific directories
3. **Get MetaKey ID** - Retrieve the MetaKey identifier (optional if already known)
4. **Create Contract Metadata** - Assign a value to the metadata field for a specific contract

**Critical Requirement**: Both account-level and directory-level visibility must be enabled for metadata to appear when retrieving contract metadata. This is an **AND condition** - both must be `true`.

---

## Prerequisites

- **Authentication**: All API calls require JWT authentication via HTTP-only cookie

  - Cookie name: Set by `JWT_AUTH_COOKIE` setting (typically `auth-token`)
  - Login endpoint: `POST /auth/login`
  - Request: `{"login_name": "user@example.com", "password": "password"}`
  - Response: Sets JWT cookie automatically

- **Account Access**: User must have access to the account
- **Directory ID**: Know the root directory ID where contracts are located
- **Contract ID**: Know the contract ID to add metadata to

---

## Step 1: Create a FREE MetaKey

**Purpose**: Define a new custom metadata field at the account level.

**Endpoint**: `POST /setting/meta/update`

**Description**: Creates a new MetaKey of type FREE (custom metadata) that will be available for your account. This defines the metadata field structure but does not make it visible yet.

### Request Format

```json
{
  "settingMeta": [
    {
      "id": 0, // REQUIRED: Must be 0 to create a new MetaKey
      "name": "Custom Field Name", // REQUIRED: Display name (max 255 chars)
      "type": 2, // REQUIRED: 2 = FREE (custom), 1 = DEFAULT (system-defined)
      "is_visible": true, // REQUIRED: Account-level visibility setting
      "status": 1 // REQUIRED: 1 = ENABLE, 0 = DISABLE
    }
  ]
}
```

### Request Field Details

- **`id`** (integer, required):
  - Must be `0` for new MetaKey creation
  - For updates, use the existing MetaKey ID
- **`name`** (string, required, max 255 characters):
  - Display name shown in the UI
  - Examples: "備考", "追加情報", "Project Code", "Internal Notes"
- **`type`** (integer, required):
  - `1` = DEFAULT (system-defined metadata, cannot be created via this endpoint)
  - `2` = FREE (custom metadata, what we're creating)
- **`is_visible`** (boolean, required):
  - Account-level visibility setting
  - Must be `true` for metadata to be visible (combined with directory-level setting)
- **`status`** (integer, required):
  - `0` = DISABLE (inactive)
  - `1` = ENABLE (active)

### Response Format

**Success Response**: `200 OK`

```json
{
  "msg": ["設定を更新しました"] // "Settings updated"
}
```

**Error Response**: `400 Bad Request`

```json
{
  // Serializer validation errors
  "settingMeta": [
    {
      "name": ["This field is required."],
      "type": ["This field is required."]
    }
  ]
}
```

### Important Notes

- The MetaKey is created with `account_id` set to the authenticated user's account
- FREE metadata keys are **account-specific** - each account has its own set
- After creation, the MetaKey ID is returned (check response or use GET endpoint)
- The MetaKey must have `status=1` (ENABLE) to be usable

### Example Request

```bash
POST /setting/meta/update
Content-Type: application/json
Cookie: auth-token=<jwt_token>

{
  "settingMeta": [
    {
      "id": 0,
      "name": "備考",
      "type": 2,
      "is_visible": true,
      "status": 1
    }
  ]
}
```

---

## Step 2: Configure Directory Settings (REQUIRED)

**Purpose**: Enable the metadata field for specific directories. This is **critical** - without this step, metadata will not appear when retrieving contract metadata, even if it exists in the database.

**Endpoint**: `POST /setting/directory/meta/update`

**Description**: Associates MetaKeys with directories and sets directory-level visibility. The GET contract metadata endpoint requires BOTH account-level AND directory-level visibility to be `true`.

### Why This Step is Required

From the code in `ContractMetaDataListView.get()`:

```python
free_key_ids = [key.id for key in root_directory.keys.filter(
    is_visible=True,                              # Account-level visibility
    meta_key_directory_key__is_visible=True,      # Directory-level visibility
    type=MetaKey.Type.FREE.value
).all()]
```

Both conditions must be met:

1. `MetaKey.is_visible = True` (account-level, set in Step 1)
2. `MetaKeyDirectory.is_visible = True` (directory-level, set in this step)

### Getting Directory Information

**Optional Step**: Get current directory metadata settings to see existing configuration.

**Endpoint**: `GET /setting/directory/meta?id=<directory_id>`

**Response Format**:

```json
{
  "response": {
    "default_list": [
      {
        "id": 1,
        "name": "契約書名",
        "type": 1,
        "is_visible": true,
        "meta_key_directory_id": 10
      }
    ],
    "free_list": [
      {
        "id": 25,
        "name": "備考",
        "type": 2,
        "is_visible": true,
        "meta_key_directory_id": 15
      }
    ]
  }
}
```

### Request Format

```json
{
  "directoryId": "123", // REQUIRED: Directory ID (as string)
  "defaultList": [
    // Array of DEFAULT metadata keys for this directory
    {
      "id": 1, // MetaKey ID
      "name": "契約書名", // Optional: can be null
      "type": "DEFAULT", // or "1"
      "is_visible": true,
      "meta_key_directory_id": 10 // null for new entries, existing ID for updates
    }
  ],
  "freeList": [
    // Array of FREE metadata keys for this directory
    {
      "id": 25, // REQUIRED: MetaKey ID from Step 1
      "name": "備考", // Optional: can be null
      "type": "FREE", // or "2"
      "is_visible": true, // REQUIRED: Must be true to see metadata
      "meta_key_directory_id": null // null for new entries
    }
  ]
}
```

### Request Field Details

- **`directoryId`** (string, required):

  - The directory ID where contracts are located
  - Typically the root directory (level=0) for the contract type
  - Contracts inherit metadata visibility from their root directory

- **`defaultList`** (array, optional):

  - List of DEFAULT metadata keys (type=1) for this directory
  - Can be empty array `[]` if only configuring FREE metadata

- **`freeList`** (array, required if adding FREE metadata):

  - List of FREE metadata keys (type=2) for this directory
  - Include the MetaKey created in Step 1

- **`id`** (integer, required):

  - The MetaKey ID from Step 1

- **`name`** (string, optional):

  - Can be `null` or the display name
  - Not strictly required for functionality

- **`type`** (string, required):

  - `"FREE"` or `"2"` for custom metadata
  - `"DEFAULT"` or `"1"` for system metadata

- **`is_visible`** (boolean, required):

  - **Must be `true`** for metadata to appear when retrieving contract metadata
  - Combined with account-level `is_visible` (AND condition)

- **`meta_key_directory_id`** (integer, nullable):
  - `null` for new directory-metadata associations
  - Existing `MetaKeyDirectory.id` if updating an existing association

### Response Format

**Success Response**: `200 OK`

```json
{
  "msg": ["登録しました"] // "Registered"
}
```

**Error Response**: `400 Bad Request`

```json
{
  "msg": ["パラメータが不正です....."] // "Invalid parameters"
}
```

**Error Cases**:

- MetaKey ID does not exist
- MetaKey does not belong to user's account (for FREE keys)
- MetaKey status is not ENABLE
- Directory does not exist or user doesn't have access

### Important Notes

- **Root Directory**: The system uses the **root directory** of a contract to determine metadata visibility
- **Inheritance**: Contracts inherit metadata settings from their root directory
- **Batch Updates**: You can configure multiple metadata keys in a single request
- **Existing Entries**: If a MetaKey-directory association already exists, include the `meta_key_directory_id` to update it
- **Removal**: To remove a metadata key from a directory, omit it from the request (or set `is_visible: false`)

### Example Request

```bash
POST /setting/directory/meta/update
Content-Type: application/json
Cookie: auth-token=<jwt_token>

{
  "directoryId": "1",
  "defaultList": [],
  "freeList": [
    {
      "id": 25,
      "name": "備考",
      "type": "FREE",
      "is_visible": true,
      "meta_key_directory_id": null
    }
  ]
}
```

---

## Step 3: Get Available FREE Metadata Keys (Optional)

**Purpose**: Retrieve the list of available FREE metadata keys to confirm creation and get the MetaKey ID.

**Endpoint**: `GET /contract/metakey/free`

**Description**: Lists all FREE metadata keys available for the current user's account that have ENABLE status.

### Response Format

```json
[
  {
    "id": 25, // MetaKey ID - use this as key_id in Step 4
    "name": "備考", // Display name
    "label": "" // System label (empty for FREE keys)
  },
  {
    "id": 26,
    "name": "追加情報",
    "label": ""
  }
]
```

### Response Field Details

- **`id`** (integer): MetaKey ID - use this as `key_id` when creating metadata
- **`name`** (string): Display name of the metadata key
- **`label`** (string): System label (usually empty for FREE keys)

### Notes

- Only returns FREE metadata keys (`type = 2`)
- Only returns keys for the current user's account
- Only returns ENABLE status keys
- If the MetaKey from Step 1 doesn't appear, check:
  - Status is ENABLE
  - Account ID matches
  - Directory configuration is complete

### Example Request

```bash
GET /contract/metakey/free
Cookie: auth-token=<jwt_token>
```

---

## Step 4: Create Contract Metadata

**Purpose**: Assign a value to the custom metadata field for a specific contract.

**Endpoint**: `PUT /contract/<contract_id>/metadata`

**Description**: Creates or updates metadata for a contract. Supports batch operations.

### URL Parameters

- **`contract_id`** (integer, required): The ID of the contract

### Request Format

```json
{
  "params": {
    "list": [
      {
        "key_id": 25, // REQUIRED for CREATE: MetaKey ID from Step 1 or 3
        "value": "Some value", // Optional: Text value (max 255 chars)
        "dateValue": "2024-01-15", // Optional: Date value (YYYY-MM-DD)
        "lock": false // Optional: Lock status (default: false)
      }
    ]
  }
}
```

### Request Field Details

**For CREATE** (when `id` is omitted):

- **`key_id`** (integer, required): MetaKey ID from Step 1/3
- **`value`** (string, optional, max 255 characters): Text value for the metadata
- **`dateValue`** (date, optional, format: YYYY-MM-DD): Date value for the metadata
- **`lock`** (boolean, optional, default: false): If `true`, prevents editing the value

**For UPDATE** (when `id` is provided):

- **`id`** (integer, required): Existing metadata record ID
- **`key_id`** (integer, optional): Cannot be specified if `id` is provided
- **`value`** (string, optional): New text value (ignored if `lock: true`)
- **`dateValue`** (date, optional): New date value (ignored if `lock: true`)
- **`lock`** (boolean, optional): Lock/unlock the metadata

### Validation Rules

1. **Cannot specify both `id` and `key_id`** in the same request item
2. **For CREATE**: `key_id` must exist and be ENABLE status
3. **For CREATE**: `key_id` must belong to user's account (for FREE keys)
4. **For CREATE**: `key_id` must be visible in the contract's root directory
5. **For UPDATE**: `id` must exist and belong to the specified contract
6. **Locked metadata**: If `lock: true`, `value` and `dateValue` updates are ignored
7. **Text length**: `value` is limited to 255 characters
8. **Date format**: `dateValue` must be in YYYY-MM-DD format

### Response Format

**Success Response**: `200 OK`

```json
{
  "response": [
    {
      "id": 123,
      "key": {
        "id": 25,
        "name": "備考",
        "label": "",
        "type": 2,
        "isVisible": true
      },
      "check": false,
      "checkedBy": null,
      "value": "Some value",
      "dateValue": null,
      "score": 0.0,
      "startOffset": 0,
      "endOffset": 0,
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

**Error Response**: `400 Bad Request`

```json
{
  "msg": "パラメータが不正です" // "Invalid parameters"
}
```

Or validation errors:

```json
{
  "list": [
    {
      "non_field_errors": ["Only one of `id` and `key_id` can be specified"]
    }
  ]
}
```

### Important Notes

- **Batch Operations**: You can create/update multiple metadata items in one request
- **Text vs Date**: Typically use either `value` (text) or `dateValue` (date), not both
- **Locked Metadata**: Once locked, only the `lock` field can be changed
- **Contract Scope**: Metadata is scoped to a specific contract
- **Reusability**: The same MetaKey can be used across multiple contracts

### Example Request

```bash
PUT /contract/123/metadata
Content-Type: application/json
Cookie: auth-token=<jwt_token>

{
  "params": {
    "list": [
      {
        "key_id": 25,
        "value": "これは備考欄の値です"
      }
    ]
  }
}
```

### Example Batch Request

```bash
PUT /contract/123/metadata
Content-Type: application/json
Cookie: auth-token=<jwt_token>

{
  "params": {
    "list": [
      {
        "key_id": 25,
        "value": "備考1"
      },
      {
        "key_id": 26,
        "value": "追加情報の値",
        "lock": true
      },
      {
        "id": 124,  // Update existing metadata
        "value": "Updated value"
      }
    ]
  }
}
```

---

## Complete Workflow Example

Here's a complete end-to-end example of adding custom metadata to a contract:

### Scenario

Add a "備考" (Notes) field to contract #123 in directory #1.

### Step-by-Step Execution

```bash
# Step 1: Create FREE MetaKey
POST /setting/meta/update
{
  "settingMeta": [{
    "id": 0,
    "name": "備考",
    "type": 2,
    "is_visible": true,
    "status": 1
  }]
}
# Response: Success - MetaKey created with id=25 (example)

# Step 2: Get available keys to confirm (optional)
GET /contract/metakey/free
# Response: [{"id": 25, "name": "備考", "label": ""}]

# Step 3: Configure directory settings (REQUIRED)
POST /setting/directory/meta/update
{
  "directoryId": "1",
  "defaultList": [],
  "freeList": [{
    "id": 25,
    "name": "備考",
    "type": "FREE",
    "is_visible": true,
    "meta_key_directory_id": null
  }]
}
# Response: {"msg": ["登録しました"]}

# Step 4: Add metadata to contract
PUT /contract/123/metadata
{
  "params": {
    "list": [{
      "key_id": 25,
      "value": "これは備考欄の値です"
    }]
  }
}
# Response: Returns created metadata object

# Step 5: Verify by retrieving contract metadata
GET /contract/123/metadata
# Response: Should include the new metadata in the response
```

---

## Common Pitfalls and Troubleshooting

### Issue: Metadata doesn't appear when retrieving contract metadata

**Symptoms**: GET `/contract/<id>/metadata` doesn't include the custom metadata, even though it was created successfully.

**Causes**:

1. **Missing directory configuration** (most common)

   - Solution: Ensure Step 2 (directory configuration) was completed
   - Check: Both account-level and directory-level `is_visible` must be `true`

2. **Wrong directory ID**

   - Solution: Use the root directory ID where the contract is located
   - Check: Contract's root directory using contract service

3. **MetaKey not enabled**

   - Solution: Ensure `status=1` (ENABLE) in Step 1

4. **Visibility settings**
   - Solution: Both `MetaKey.is_visible` and `MetaKeyDirectory.is_visible` must be `true`

### Issue: "パラメータが不正です" error

**Causes**:

1. **Invalid MetaKey ID**

   - Solution: Verify MetaKey exists and belongs to your account
   - Check: Use GET `/contract/metakey/free` to see available keys

2. **MetaKey not in directory**

   - Solution: Ensure Step 2 was completed for the contract's root directory

3. **Contract doesn't exist or no access**
   - Solution: Verify contract ID and account access

### Issue: "Only one of `id` and `key_id` can be specified"

**Cause**: Trying to both update (using `id`) and create (using `key_id`) in the same request item.

**Solution**: Use `id` for updates, `key_id` for creates. Never both.

### Issue: Locked metadata cannot be updated

**Symptom**: PUT request succeeds but value doesn't change.

**Cause**: Metadata has `lock: true`.

**Solution**: First unlock the metadata by setting `lock: false`, then update the value.

---

## Data Model Relationships

Understanding the data models helps troubleshoot issues:

### MetaKey

- **Purpose**: Defines a metadata field structure
- **Scope**: Account-level (for FREE keys)
- **Key Fields**:
  - `id`: Primary key
  - `name`: Display name
  - `type`: 1 (DEFAULT) or 2 (FREE)
  - `is_visible`: Account-level visibility
  - `status`: 0 (DISABLE) or 1 (ENABLE)
  - `account_id`: Account that owns this key (null for DEFAULT)

### MetaKeyDirectory

- **Purpose**: Associates MetaKeys with directories and sets directory-level visibility
- **Scope**: Directory-level
- **Key Fields**:
  - `key_id`: Foreign key to MetaKey
  - `directory_id`: Foreign key to Directory
  - `is_visible`: Directory-level visibility
  - `account_id`: Account that owns this association

### MetaData

- **Purpose**: Stores actual metadata values for contracts
- **Scope**: Contract-level
- **Key Fields**:
  - `id`: Primary key
  - `contract_id`: Foreign key to Contract
  - `key_id`: Foreign key to MetaKey
  - `value`: Text value (max 255 chars)
  - `date_value`: Date value
  - `lock`: Whether editing is locked
  - `status`: 0 (DISABLE) or 1 (ENABLE)

### Visibility Logic

```
Metadata is visible if:
  MetaKey.is_visible = TRUE (account-level)
  AND
  MetaKeyDirectory.is_visible = TRUE (directory-level)
  AND
  MetaKey.status = ENABLE
  AND
  MetaKeyDirectory.status = ENABLE
  AND
  MetaData.status = ENABLE (for existing values)
```

---

## API Endpoint Summary

| Step         | Method | Endpoint                              | Purpose                         |
| ------------ | ------ | ------------------------------------- | ------------------------------- |
| 1            | POST   | `/setting/meta/update`                | Create FREE MetaKey             |
| 2 (Optional) | GET    | `/setting/directory/meta?id=<dir_id>` | Get directory metadata settings |
| 2            | POST   | `/setting/directory/meta/update`      | Configure directory metadata    |
| 3 (Optional) | GET    | `/contract/metakey/free`              | List available FREE MetaKeys    |
| 4            | PUT    | `/contract/<contract_id>/metadata`    | Create/update contract metadata |
| Verify       | GET    | `/contract/<contract_id>/metadata`    | Retrieve contract metadata      |

---

## Validation Checklist for AI Agents

When implementing this workflow, ensure:

1. ✅ **Authentication cookie** is included in all requests
2. ✅ **Step 1**: MetaKey created with `id=0`, `type=2`, `status=1`, `is_visible=true`
3. ✅ **Step 2**: Directory configuration includes the MetaKey with `is_visible=true`
4. ✅ **Step 2**: Directory ID is the root directory where contracts are located
5. ✅ **Step 4**: `key_id` matches the MetaKey ID from Step 1
6. ✅ **Step 4**: For CREATE, use `key_id` (not `id`)
7. ✅ **Step 4**: For UPDATE, use `id` (not `key_id`)
8. ✅ **Value constraints**: Text values max 255 chars, dates in YYYY-MM-DD format
9. ✅ **Error handling**: Check response status codes and error messages
10. ✅ **Verification**: GET contract metadata to confirm creation

---

## Additional Notes

- **Account Scoping**: All FREE metadata keys are account-specific
- **Directory Inheritance**: Contracts inherit metadata settings from their root directory
- **Batch Operations**: Multiple metadata items can be created/updated in a single request
- **Soft Delete**: Metadata deletion sets `status=DISABLE`, not physical deletion
- **Locked Metadata**: Locked metadata cannot have values updated (only lock status can change)
- **Date vs Text**: Use either `value` (text) or `dateValue` (date), typically not both
- **Reusability**: Once created, a MetaKey can be reused across multiple contracts and directories

---

**Last Updated**: Based on codebase analysis  
**Version**: 1.0
