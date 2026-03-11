# Metadata API Comprehensive Documentation

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Metadata Types](#metadata-types)
4. [Contract Metadata APIs](#contract-metadata-apis)
5. [Metadata Key Management APIs](#metadata-key-management-apis)
6. [Directory Metadata Configuration APIs](#directory-metadata-configuration-apis)
7. [CSV Import/Export APIs](#csv-importexport-apis)
8. [Helper/Utility APIs](#helperutility-apis)
9. [Data Models](#data-models)
10. [Error Handling](#error-handling)
11. [Best Practices](#best-practices)

---

## Overview

This document provides comprehensive documentation for all metadata-related APIs in the ConPass system. Metadata in ConPass allows you to attach structured information to contracts, enabling better organization, search, and management of contract data.

The metadata system supports:

- **System-defined (DEFAULT) metadata**: Pre-configured fields like contract title, dates, company names
- **Custom (FREE) metadata**: User-defined fields specific to your account
- **Directory-level visibility**: Control which metadata fields are visible in different contract directories
- **Bulk operations**: CSV import/export for efficient metadata management

---

## Authentication

All metadata APIs require authentication via JWT token stored in HTTP cookies.

- **Cookie Name**: Set by `JWT_AUTH_COOKIE` setting (typically `auth-token`)
- **Authentication Method**: JWT token in HTTP-only cookie
- **Login Endpoint**: `POST /auth/login`
  - Request: `{"login_name": "user@example.com", "password": "password"}`
  - Response: Sets JWT cookie automatically

**Important**: All API requests must include the authentication cookie. The system automatically validates the user's account and permissions.

---

## Metadata Types

The system supports two types of metadata:

### 1. DEFAULT Metadata (`type = 1`)

- System-defined metadata fields (e.g., contract title, company name, dates)
- Cannot be created or deleted by users
- Visibility can be controlled at account and directory levels
- Examples: 契約書名 (Contract Title), 契約日 (Contract Date), 契約開始日 (Start Date), 契約終了日 (End Date), 担当者名 (Assigned Person)

### 2. FREE/Custom Metadata (`type = 2`)

- User-defined custom metadata fields
- Can be created, updated, and deleted by users within their account scope
- Account-specific (not shared across accounts)
- Examples: Custom fields like "備考" (Notes), "部門" (Department), etc.

---

## Contract Metadata APIs

### 1. Get Contract Metadata

**Endpoint**: `GET /contract/<contract_id>/metadata`

**Description**: Retrieves all metadata for a specific contract. Returns both DEFAULT and FREE metadata that are visible based on account and directory settings. The system uses the root directory of the contract to determine which metadata fields are visible.

**URL Parameters**:

- `contract_id` (integer, required): The ID of the contract

**Request Headers**:

- Cookie: JWT authentication token

**Response Format**:

```json
[
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
  },
  {
    "id": null,
    "key": {
      "id": 10,
      "name": "Custom Field",
      "label": "",
      "type": 2,
      "isVisible": true
    },
    "value": null,
    "dateValue": null,
    "lock": false
  }
]
```

**Response Fields**:

- `id`: Metadata record ID (null for unused FREE metadata keys that are visible but not yet filled)
- `key`: Metadata key information
  - `id`: MetaKey ID
  - `name`: Display name (e.g., "契約書名")
  - `label`: System label (e.g., "title", "conpass_person")
  - `type`: 1 for DEFAULT, 2 for FREE
  - `isVisible`: Whether the key is visible
- `value`: Text value (string, max 255 characters)
- `dateValue`: Date value (YYYY-MM-DD format, null if not a date field)
- `lock`: Whether the metadata is locked (locked metadata cannot be updated)
- `status`: 1 for ENABLE, 0 for DISABLE
- `createdAt`, `updatedAt`: Timestamps
- `createdBy`, `updatedBy`: User information

**Special Handling**:

- For "担当者名" (Assigned Person) fields, multiple values are combined with commas
- Only metadata with `status = ENABLE` is returned
- Visibility is determined by both account-level and directory-level settings (AND condition)

**Error Responses**:

- `400 Bad Request`: Contract not found
  ```json
  { "msg": ["契約書が見つかりません"] }
  ```

**Example**:

```bash
GET /contract/123/metadata
Cookie: auth-token=<jwt_token>
```

---

### 2. Create/Update Contract Metadata

**Endpoint**: `PUT /contract/<contract_id>/metadata`

**Description**: Creates new metadata records or updates existing ones for a contract. Supports batch operations (multiple metadata items in a single request). When updating the contract title metadata (key.label = "title"), the contract name is also automatically updated.

**URL Parameters**:

- `contract_id` (integer, required): The ID of the contract

**Request Headers**:

- Cookie: JWT authentication token
- Content-Type: application/json

**Request Body**:

```json
{
  "params": {
    "list": [
      {
        "id": 123,
        "value": "Updated value"
      },
      {
        "key_id": 5,
        "value": "New metadata value"
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

**Request Fields**:

- `list` (array, required): Array of metadata items to create or update
  - For **UPDATE**: Include `id` (metadata record ID). Do not include `key_id`.
  - For **CREATE**: Include `key_id` (MetaKey ID). Do not include `id`.
  - `value` (string, optional): Text value (max 255 characters). Cannot update if metadata is locked.
  - `dateValue` (string, optional): Date value in YYYY-MM-DD format. Cannot update if metadata is locked.
  - `lock` (boolean, optional): Lock/unlock the metadata. Locked metadata cannot have `value` or `dateValue` updated.

**Special Handling for Person Metadata**:

- For metadata with `key.label = "conpass_person"`, the `value` field accepts comma-separated person names
- The system automatically creates individual person records for each name

**Response Format**:

```json
[
  {
    "id": 123,
    "key": {
      "id": 5,
      "name": "契約書名",
      "label": "title",
      "type": 1,
      "isVisible": true
    },
    "value": "Updated value",
    "dateValue": null,
    "lock": false,
    "status": 1
  }
]
```

**Error Responses**:

- `400 Bad Request`: Invalid parameters or metadata not found
  ```json
  { "msg": ["パラメータが不正です"] }
  ```

**Notes**:

- Cannot specify both `id` and `key_id` in the same item
- Locked metadata cannot have `value` or `dateValue` updated (but `lock` can be changed)
- Date values must be in YYYY-MM-DD format
- Text values are limited to 255 characters
- Batch operations are supported (multiple items in one request)

**Example**:

```bash
PUT /contract/123/metadata
Content-Type: application/json
Cookie: auth-token=<jwt_token>

{
  "params": {
    "list": [
      {
        "key_id": 10,
        "value": "Custom value"
      }
    ]
  }
}
```

---

### 3. Delete Contract Metadata

**Endpoint**: `DELETE /contract/metadata/<metadata_id>`

**Description**: Soft-deletes a metadata record (sets status to DISABLE). The record is not physically removed but marked as inactive and will not appear in GET requests.

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
Cookie: auth-token=<jwt_token>
```

---

## Metadata Key Management APIs

### 4. Get All Metadata Keys (Settings)

**Endpoint**: `GET /setting/meta`

**Description**: Retrieves all metadata keys (both DEFAULT and FREE) available for the current account, including their visibility settings. This is used for metadata configuration in the settings page.

**Request Headers**:

- Cookie: JWT authentication token

**Response Format**:

```json
[
  {
    "id": 1,
    "name": "契約書名",
    "label": "title",
    "type": 1,
    "is_visible": true,
    "status": 1,
    "accountId": null
  },
  {
    "id": 10,
    "name": "Custom Field",
    "label": "",
    "type": 2,
    "is_visible": true,
    "status": 1,
    "accountId": 123
  }
]
```

**Response Fields**:

- `id`: MetaKey ID
- `name`: Display name
- `label`: System label (for DEFAULT keys)
- `type`: 1 for DEFAULT, 2 for FREE
- `is_visible`: Whether the key is visible at account level
- `status`: 1 for ENABLE, 0 for DISABLE
- `accountId`: Account ID (null for DEFAULT keys, account ID for FREE keys)

**Notes**:

- DEFAULT keys have `accountId: null` and may have account-specific visibility via `CompanyMetaKey`
- FREE keys have `accountId` set to the account that created them
- Only ENABLE status keys are returned

**Example**:

```bash
GET /setting/meta
Cookie: auth-token=<jwt_token>
```

---

### 5. Update Metadata Key Settings

**Endpoint**: `POST /setting/meta/update`

**Description**: Updates metadata key visibility settings at the account level. Can also create new FREE metadata keys. For DEFAULT keys, this updates the `CompanyMetaKey` visibility. For FREE keys, this updates the `MetaKey` itself or creates a new one.

**Request Headers**:

- Cookie: JWT authentication token
- Content-Type: application/json

**Request Body**:

```json
{
  "settingMeta": [
    {
      "id": 1,
      "type": 1,
      "is_visible": true
    },
    {
      "id": 0,
      "type": 2,
      "name": "New Custom Field",
      "is_visible": true,
      "status": 1
    },
    {
      "id": 10,
      "type": 2,
      "is_visible": false
    }
  ]
}
```

**Request Fields**:

- `settingMeta` (array, required): Array of metadata key settings
  - `id` (integer, required): MetaKey ID. Use `0` to create a new FREE key.
  - `type` (integer, required): 1 for DEFAULT, 2 for FREE
  - `is_visible` (boolean, required): Visibility setting
  - `name` (string, required for new FREE keys): Name of the new metadata key
  - `status` (integer, required for new FREE keys): 1 for ENABLE, 0 for DISABLE

**Response Format**:

```json
{
  "msg": ["設定を更新しました"]
}
```

**Error Responses**:

- `400 Bad Request`: Invalid parameters
  ```json
  { "msg": ["パラメータが不正です"] }
  ```

**Notes**:

- For DEFAULT keys: Updates or creates `CompanyMetaKey` record for account-level visibility
- For FREE keys with `id = 0`: Creates a new `MetaKey` record
- For FREE keys with existing `id`: Updates the `is_visible` field
- Cannot delete DEFAULT keys (they are system-defined)
- FREE keys can be disabled by setting `status = 0`, but this should be done carefully as it affects all contracts using that key

**Example**:

```bash
POST /setting/meta/update
Content-Type: application/json
Cookie: auth-token=<jwt_token>

{
  "settingMeta": [
    {
      "id": 0,
      "type": 2,
      "name": "備考",
      "is_visible": true,
      "status": 1
    }
  ]
}
```

---

## Directory Metadata Configuration APIs

### 6. Get Directory Metadata Settings

**Endpoint**: `GET /setting/directory/meta?id=<directory_id>`

**Description**: Retrieves metadata key visibility settings for a specific directory. Returns both DEFAULT and FREE metadata keys with their directory-specific visibility settings.

**Query Parameters**:

- `id` (integer, required): Directory ID

**Request Headers**:

- Cookie: JWT authentication token

**Response Format**:

```json
{
  "default_list": [
    {
      "id": 1,
      "name": "契約書名",
      "type": 1,
      "is_visible": true,
      "meta_key_directory_id": 5
    }
  ],
  "free_list": [
    {
      "id": 10,
      "name": "Custom Field",
      "type": 2,
      "is_visible": true,
      "meta_key_directory_id": 12
    }
  ]
}
```

**Response Fields**:

- `default_list`: Array of DEFAULT metadata keys
- `free_list`: Array of FREE metadata keys
- Each item contains:
  - `id`: MetaKey ID
  - `name`: Display name
  - `type`: 1 for DEFAULT, 2 for FREE
  - `is_visible`: Visibility setting for this directory
  - `meta_key_directory_id`: MetaKeyDirectory ID (null if not configured)

**Notes**:

- If `meta_key_directory_id` is null, the metadata key is not yet configured for this directory
- The default visibility for DEFAULT keys is `true` if not configured
- Only ENABLE status metadata keys are returned

**Example**:

```bash
GET /setting/directory/meta?id=1
Cookie: auth-token=<jwt_token>
```

---

### 7. Update Directory Metadata Settings

**Endpoint**: `POST /setting/directory/meta/update`

**Description**: Updates metadata key visibility settings for a specific directory. Creates or updates `MetaKeyDirectory` records that control which metadata fields are visible for contracts in that directory.

**Request Headers**:

- Cookie: JWT authentication token
- Content-Type: application/json

**Request Body**:

```json
{
  "directoryId": 1,
  "defaultList": [
    {
      "id": 1,
      "name": "契約書名",
      "type": 1,
      "is_visible": true,
      "meta_key_directory_id": null
    }
  ],
  "freeList": [
    {
      "id": 10,
      "name": "Custom Field",
      "type": 2,
      "is_visible": true,
      "meta_key_directory_id": null
    }
  ]
}
```

**Request Fields**:

- `directoryId` (integer, required): Directory ID
- `defaultList` (array, optional): Array of DEFAULT metadata key settings
- `freeList` (array, optional): Array of FREE metadata key settings
- Each item contains:
  - `id` (integer, required): MetaKey ID
  - `name` (string, required): Display name
  - `type` (integer, required): 1 for DEFAULT, 2 for FREE
  - `is_visible` (boolean, required): Visibility setting for this directory
  - `meta_key_directory_id` (integer, nullable): Existing MetaKeyDirectory ID if updating, null if creating new

**Response Format**:

```json
{
  "msg": ["登録しました"]
}
```

**Error Responses**:

- `400 Bad Request`: Invalid parameters or MetaKey not found
  ```json
  { "msg": ["パラメータが不正です....."] }
  ```

**Notes**:

- The system uses the **root directory** of a contract to determine metadata visibility
- Contracts inherit metadata settings from their root directory
- Batch updates are supported (multiple metadata keys in a single request)
- If a MetaKey-directory association already exists, include `meta_key_directory_id` to update it
- To remove a metadata key from a directory, omit it from the request (or set `is_visible: false`)
- Visibility is determined by AND condition: account-level `is_visible` AND directory-level `is_visible`

**Example**:

```bash
POST /setting/directory/meta/update
Content-Type: application/json
Cookie: auth-token=<jwt_token>

{
  "directoryId": 1,
  "defaultList": [],
  "freeList": [
    {
      "id": 25,
      "name": "備考",
      "type": 2,
      "is_visible": true,
      "meta_key_directory_id": null
    }
  ]
}
```

---

### 8. Get Root Directories for Metadata Settings

**Endpoint**: `GET /setting/meta/directory?type=<type>`

**Description**: Retrieves root directories (parent directories with no parent) for a specific type. Used to get the list of directories where metadata settings can be configured.

**Query Parameters**:

- `type` (integer, required): Directory type

**Request Headers**:

- Cookie: JWT authentication token

**Response Format**:

```json
[
  {
    "id": 1,
    "name": "Root Directory",
    "type": 1,
    "level": 0,
    "status": 1
  }
]
```

**Notes**:

- Only returns root directories (level = 0)
- Only returns ENABLE status directories
- Filtered by account

**Example**:

```bash
GET /setting/meta/directory?type=1
Cookie: auth-token=<jwt_token>
```

---

## CSV Import/Export APIs

### 9. Download Contract Metadata CSV

**Endpoint**: `GET /contract/meta/csv/download`

**Description**: Downloads a CSV file containing metadata for contracts matching the search criteria. The CSV includes both DEFAULT and FREE metadata fields, with FREE fields appended as additional columns.

**Query Parameters**:

- All parameters from `ContractListRequestBodySerializer` (contract search parameters)
- See contract search API documentation for available parameters

**Request Headers**:

- Cookie: JWT authentication token

**Response Format**:

- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename="conpass_metadata_YYYYMMDDHHMMSS.csv"`
- UTF-8 BOM encoded

**CSV Format**:

- First row: Headers (base headers + FREE metadata key names)
- Subsequent rows: Contract data with metadata values
- Date fields: YYYY-MM-DD format
- Person fields: Comma-separated values

**Response Fields** (CSV columns):

- Base columns from sample CSV (契約書 ID, 契約書名, etc.)
- Additional columns for each FREE metadata key (dynamic based on account)

**Error Responses**:

- `200 OK` with message: No contracts found
  ```json
  { "message": "対象はありません" }
  ```
- `404 Not Found`: Sample CSV file not found
  ```json
  { "error": "サンプルCSVファイルが見つかりません" }
  ```

**Notes**:

- Uses a sample CSV file as a template
- FREE metadata keys are dynamically added as columns
- Only includes contracts that match the search criteria
- Only includes ENABLE status metadata

**Example**:

```bash
GET /contract/meta/csv/download?search=keyword
Cookie: auth-token=<jwt_token>
```

---

### 10. Download Blank Contract Metadata CSV Template

**Endpoint**: `GET /contract/meta/blank/csv/download`

**Description**: Downloads a blank CSV template file for metadata import. The template includes all base columns plus columns for all FREE metadata keys, but excludes the PDF name column.

**Request Headers**:

- Cookie: JWT authentication token

**Response Format**:

- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename="conpass_metadata_template_YYYYMMDDHHMMSS.csv"`
- UTF-8 BOM encoded

**CSV Format**:

- First row: Headers (base headers + FREE metadata key names, PDF name column removed)
- Next 3 rows: Sample data rows (for reference)

**Notes**:

- PDF name column is removed from the template
- FREE metadata keys are dynamically added as columns
- Includes sample data rows for reference

**Example**:

```bash
GET /contract/meta/blank/csv/download
Cookie: auth-token=<jwt_token>
```

---

### 11. Upload Contract Metadata CSV

**Endpoint**: `POST /contract/meta/csv/upload`

**Description**: Uploads a CSV file to create or update contract metadata in bulk. The CSV file should match the format from the download endpoints.

**Request Headers**:

- Cookie: JWT authentication token
- Content-Type: `multipart/form-data`

**Request Body** (Form Data):

- `csv` (file, required): CSV file to upload

**Response Format**:

```json
{
  "success": true,
  "msg": "Metadata imported successfully"
}
```

**Error Responses**:

- `400 Bad Request`: CSV file not provided or invalid
  ```json
  {
    "success": false,
    "msg": "CSVファイルが提供されていません"
  }
  ```
  or
  ```json
  {
    "success": false,
    "msg": "CSVデータが無効です",
    "errors": [...]
  }
  ```
- `500 Internal Server Error`: Server error during import
  ```json
  {
    "success": false,
    "msg": "エラーが発生しました",
    "error_message": "...",
    "stack_trace": "..."
  }
  ```

**CSV Format Requirements**:

- Must match the format from download endpoints
- UTF-8 encoding (BOM is automatically handled)
- Required columns: Contract ID, MetaKey ID, etc.
- Date values in YYYY-MM-DD format
- Person values as comma-separated names

**Notes**:

- Uses `MetaDataCsvImporter` service for validation and import
- Validates CSV structure before importing
- Supports both create and update operations
- Errors are reported in the response if validation fails

**Example**:

```bash
POST /contract/meta/csv/upload
Content-Type: multipart/form-data
Cookie: auth-token=<jwt_token>

csv: <file>
```

---

### 12. Download Metadata Settings CSV

**Endpoint**: `GET /setting/meta/csv/download?metaKeyIds=<comma_separated_ids>`

**Description**: Downloads a CSV file containing all metadata values for specified metadata keys across all contracts in the account. Used for bulk export of specific metadata fields.

**Query Parameters**:

- `metaKeyIds` (string, required): Comma-separated list of MetaKey IDs

**Request Headers**:

- Cookie: JWT authentication token

**Response Format**:

- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename="conpass_metadata_YYYYMMDDHHMMSS.csv"`
- UTF-8 encoded

**CSV Format**:

- Headers: `契約書ID（変更不可）`, `メタキーID（変更不可）`, `メタデータID（変更不可）`, `項目名（変更不可）`, `値`, `値（日付）`
- Each row represents one metadata value

**Response Fields** (CSV columns):

- `契約書ID（変更不可）`: Contract ID
- `メタキーID（変更不可）`: MetaKey ID
- `メタデータID（変更不可）`: MetaData ID (for updates)
- `項目名（変更不可）`: Metadata key name
- `値`: Text value
- `値（日付）`: Date value (YYYY-MM-DD format)

**Error Responses**:

- `400 Bad Request`: Invalid parameters
  ```json
  { "msg": ["パラメータが不正です"] }
  ```
- `500 Internal Server Error`: Server error
  ```json
  { "detail": "後ほど再試行してください。" }
  ```

**Notes**:

- Only includes ENABLE status metadata
- Only includes contracts from the user's account
- Date values are in YYYY-MM-DD format
- Useful for bulk updates via CSV upload

**Example**:

```bash
GET /setting/meta/csv/download?metaKeyIds=1,2,10
Cookie: auth-token=<jwt_token>
```

---

### 13. Upload Metadata Settings CSV

**Endpoint**: `POST /setting/meta/csv/update`

**Description**: Uploads a CSV file to bulk update metadata values. The CSV should match the format from the download endpoint.

**Request Headers**:

- Cookie: JWT authentication token
- Content-Type: application/json

**Request Body**:

```json
{
  "csvSettingMeta": [
    {
      "metadataId": 123,
      "contractId": 456,
      "metakeyId": 1,
      "value": "Updated value",
      "dateValue": "2024-12-31",
      "lineNum": 2
    },
    {
      "contractId": 457,
      "metakeyId": 1,
      "value": "New value",
      "dateValue": null,
      "lineNum": 3
    }
  ]
}
```

**Request Fields**:

- `csvSettingMeta` (array, required): Array of CSV row data
  - `metadataId` (integer, optional): MetaData ID for updates (omit for creates)
  - `contractId` (integer, required): Contract ID
  - `metakeyId` (integer, required): MetaKey ID
  - `value` (string, optional): Text value
  - `dateValue` (string, optional): Date value in YYYY-MM-DD format
  - `lineNum` (integer, required): Line number in CSV (for error reporting)

**Response Format**:

```json
{
  "msg": ["設定を更新しました"],
  "error_list": [
    {
      "lineNum": 5,
      "reason": "存在しないメタデータIDです"
    }
  ]
}
```

**Error Responses**:

- `400 Bad Request`: Invalid parameters
  ```json
  { "msg": ["パラメータが不正です"] }
  ```
- `500 Internal Server Error`: Database error
  ```json
  { "msg": ["DBエラーが発生しました"] }
  ```

**Error List Items**:

- `lineNum`: Line number in CSV
- `reason`: Error reason (e.g., "存在しないメタデータ ID です", "ロックされています", "日付のフォーマットは YYYY-MM-DD です")

**Notes**:

- If `metadataId` is provided, updates existing metadata
- If `metadataId` is omitted, creates new metadata
- Locked metadata cannot be updated
- Date values must be in YYYY-MM-DD format
- Errors are collected and returned in `error_list` (non-blocking)

**Example**:

```bash
POST /setting/meta/csv/update
Content-Type: application/json
Cookie: auth-token=<jwt_token>

{
  "csvSettingMeta": [
    {
      "metadataId": 123,
      "contractId": 456,
      "metakeyId": 1,
      "value": "Updated",
      "lineNum": 2
    }
  ]
}
```

---

### 14. Download Contract Metadata CSV (Settings)

**Endpoint**: `GET /setting/contract/meta/csv/download?createDateFrom=<date>&createDateTo=<date>`

**Description**: Downloads a CSV file containing contract information with metadata for contracts created within a date range. This is a specialized export for contract management.

**Query Parameters**:

- `createDateFrom` (string, required): Start date in datetime-local format (YYYY-MM-DDTHH:mm)
- `createDateTo` (string, required): End date in datetime-local format (YYYY-MM-DDTHH:mm)

**Request Headers**:

- Cookie: JWT authentication token

**Response Format**:

- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename="conpass_contract_metadata_YYYYMMDDHHMMSS.csv"`
- UTF-8 BOM encoded

**CSV Format**:

- Headers: `契約書ID`, `登録日時`, `登録者名`, `PDFファイル名`, `契約書タイトル`, `契約書タイプ`, `契約書ステータス`, `格納フォルダ名`, `フォルダ種別`
- Each row represents one contract

**Response Fields** (CSV columns):

- `契約書ID`: Contract ID
- `登録日時`: Creation date/time (YYYY-MM-DD HH:mm format)
- `登録者名`: Creator username
- `PDFファイル名`: PDF file name
- `契約書タイトル`: Contract title (from metadata key_id=1)
- `契約書タイプ`: Contract type ("契約書" or "契約書テンプレート")
- `契約書ステータス`: Contract status ("未採用", "採用済", "締結済", "解約", "契約満了")
- `格納フォルダ名`: Directory name
- `フォルダ種別`: Directory level ("親" or "子")

**Error Responses**:

- `400 Bad Request`: Invalid parameters
  ```json
  { "msg": ["パラメータが不正です"] }
  ```
- `200 OK` with message: No contracts found
  ```json
  { "msg": ["対象のファイルがありません"] }
  ```
- `500 Internal Server Error`: Server error
  ```json
  { "detail": "後ほど再試行してください。" }
  ```

**Notes**:

- Only includes contracts with status: UNUSED, USED, SIGNED_BY_PAPER, CANCELED, EXPIRED
- Excludes garbage contracts (`is_garbage=False`)
- Date range is inclusive (from 00:00:00 to 23:59:59.999999)
- Contract title is extracted from metadata with `key_id=1`

**Example**:

```bash
GET /setting/contract/meta/csv/download?createDateFrom=2024-01-01T00:00&createDateTo=2024-12-31T23:59
Cookie: auth-token=<jwt_token>
```

---

## Helper/Utility APIs

### 15. Get Available FREE Metadata Keys

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
- `label`: System label (empty for FREE keys)

**Notes**:

- Only returns FREE metadata keys (type = 2)
- Only returns ENABLE status keys
- Only returns keys for the current user's account
- Ordered by ID

**Example**:

```bash
GET /contract/metakey/free
Cookie: auth-token=<jwt_token>
```

---

## Data Models

### MetaKey

Represents a metadata key definition.

**Fields**:

- `id`: Primary key
- `name`: Display name (e.g., "契約書名")
- `label`: System label (e.g., "title", "conpass_person")
- `type`: 1 for DEFAULT, 2 for FREE
- `status`: 1 for ENABLE, 0 for DISABLE
- `is_visible`: Visibility at account level
- `account_id`: Account ID (null for DEFAULT keys)
- `created_at`, `updated_at`: Timestamps
- `created_by`, `updated_by`: User references

### MetaData

Represents a metadata value for a contract.

**Fields**:

- `id`: Primary key
- `contract_id`: Contract reference
- `key_id`: MetaKey reference
- `value`: Text value (max 255 characters)
- `date_value`: Date value
- `status`: 1 for ENABLE, 0 for DISABLE
- `lock`: Whether metadata is locked
- `check`: Verification flag
- `checked_by`: User who verified
- `score`: Confidence score (for AI-extracted values)
- `start_offset`, `end_offset`: Text position (for AI-extracted values)
- `created_at`, `updated_at`: Timestamps
- `created_by`, `updated_by`: User references

### CompanyMetaKey

Represents account-level visibility settings for DEFAULT metadata keys.

**Fields**:

- `id`: Primary key
- `account_id`: Account reference
- `meta_key_id`: MetaKey reference
- `is_visible`: Visibility setting
- `status`: 1 for ENABLE, 0 for DISABLE
- `created_at`, `updated_at`: Timestamps
- `created_by`, `updated_by`: User references

### MetaKeyDirectory

Represents directory-level visibility settings for metadata keys.

**Fields**:

- `id`: Primary key
- `key_id`: MetaKey reference
- `directory_id`: Directory reference
- `account_id`: Account reference
- `is_visible`: Visibility setting for this directory
- `status`: 1 for ENABLE, 0 for DISABLE
- `created_at`, `updated_at`: Timestamps
- `created_by`, `updated_by`: User references

---

## Error Handling

### Common Error Responses

**400 Bad Request**:

```json
{
  "msg": ["エラーメッセージ"]
}
```

**500 Internal Server Error**:

```json
{
  "detail": "後ほど再試行してください。"
}
```

or

```json
{
  "msg": ["DBエラーが発生しました"]
}
```

### Error Codes and Messages

| Error Message                        | Description                | Solution                                      |
| ------------------------------------ | -------------------------- | --------------------------------------------- |
| `契約書が見つかりません`             | Contract not found         | Verify contract ID and account access         |
| `メタデータが見つかりません`         | Metadata not found         | Verify metadata ID and status                 |
| `パラメータが不正です`               | Invalid parameters         | Check request body format and required fields |
| `存在しないメタデータIDです`         | Metadata ID does not exist | Verify metadata ID in CSV upload              |
| `存在しない契約IDです`               | Contract ID does not exist | Verify contract ID in CSV upload              |
| `存在しないメタキーIDです`           | MetaKey ID does not exist  | Verify MetaKey ID and account access          |
| `ロックされています`                 | Metadata is locked         | Unlock metadata before updating               |
| `日付のフォーマットはYYYY-MM-DDです` | Invalid date format        | Use YYYY-MM-DD format for dates               |
| `対象はありません`                   | No matching contracts      | Adjust search criteria                        |
| `対象のファイルがありません`         | No files found             | Adjust date range or filters                  |

---

## Best Practices

### 1. Metadata Key Management

- **Create FREE keys before use**: Create custom metadata keys via `/setting/meta/update` before using them in contracts
- **Configure directory visibility**: Set up directory-level visibility via `/setting/directory/meta/update` to control which fields appear in different directories
- **Use meaningful names**: Choose clear, descriptive names for FREE metadata keys
- **Plan before disabling**: Disabling a metadata key affects all contracts using it

### 2. Contract Metadata Operations

- **Batch operations**: Use batch create/update operations when possible to reduce API calls
- **Check visibility**: Verify metadata keys are visible before attempting to create metadata
- **Handle locked metadata**: Check `lock` status before updating values
- **Use root directory**: Remember that contracts use their root directory for metadata visibility

### 3. CSV Operations

- **Download template first**: Use `/contract/meta/blank/csv/download` to get the correct format
- **Validate before upload**: Check CSV format matches the template
- **Handle errors**: Process `error_list` from CSV upload responses
- **Use appropriate endpoints**: Use `/setting/meta/csv/download` for settings export, `/contract/meta/csv/download` for contract metadata export

### 4. Performance Considerations

- **Batch operations**: Group multiple metadata updates in a single request
- **Filter contracts**: Use search parameters in CSV download to limit results
- **Date ranges**: Use specific date ranges in exports to reduce data volume

### 5. Security and Permissions

- **Account scoping**: All operations are automatically scoped to the user's account
- **Directory access**: Users can only access contracts in directories they have permission for
- **Validation**: Always validate that contract IDs and metadata IDs belong to the user's account

### 6. Special Field Handling

- **Person metadata**: Use comma-separated values for person fields (key.label = "conpass_person")
- **Date fields**: Always use YYYY-MM-DD format for date values
- **Contract title**: Updating title metadata (key.label = "title") also updates the contract name
- **Lock mechanism**: Use lock to prevent accidental updates to critical metadata

---

## API Endpoint Summary

| Method | Endpoint                              | Description                                     |
| ------ | ------------------------------------- | ----------------------------------------------- |
| GET    | `/contract/<contract_id>/metadata`    | Get all metadata for a contract                 |
| PUT    | `/contract/<contract_id>/metadata`    | Create/Update metadata (batch)                  |
| DELETE | `/contract/metadata/<metadata_id>`    | Delete metadata (soft delete)                   |
| GET    | `/contract/metakey/free`              | Get available FREE metadata keys                |
| GET    | `/setting/meta`                       | Get all metadata keys (settings)                |
| POST   | `/setting/meta/update`                | Update metadata key settings / Create FREE keys |
| GET    | `/setting/directory/meta?id=<id>`     | Get directory metadata settings                 |
| POST   | `/setting/directory/meta/update`      | Update directory metadata settings              |
| GET    | `/setting/meta/directory?type=<type>` | Get root directories for metadata settings      |
| GET    | `/contract/meta/csv/download`         | Download contract metadata CSV                  |
| GET    | `/contract/meta/blank/csv/download`   | Download blank metadata CSV template            |
| POST   | `/contract/meta/csv/upload`           | Upload contract metadata CSV                    |
| GET    | `/setting/meta/csv/download`          | Download metadata settings CSV                  |
| POST   | `/setting/meta/csv/update`            | Upload metadata settings CSV                    |
| GET    | `/setting/contract/meta/csv/download` | Download contract metadata CSV (settings)       |

---

## Version History

- **Version 1.0** (Current): Initial comprehensive documentation
  - All metadata APIs documented
  - CSV import/export APIs included
  - Directory-level configuration APIs included
  - Helper and utility APIs included

---

**Last Updated**: Based on codebase analysis of `app/conpass/views/contract/views.py`, `app/conpass/views/setting/views.py`, and related services
**Maintained By**: ConPass Development Team
