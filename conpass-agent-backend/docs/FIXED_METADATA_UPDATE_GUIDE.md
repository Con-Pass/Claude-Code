# Fixed Metadata Update Guide

## Overview

This document provides comprehensive details about all fixed (DEFAULT) metadata fields in contracts, including their data types, update methods, and special handling requirements. Fixed metadata are system-defined fields that cannot be created or deleted by users, but their values can be updated.

## Table of Contents

1. [Introduction](#introduction)
2. [Metadata Update Endpoint](#metadata-update-endpoint)
3. [Fixed Metadata Types](#fixed-metadata-types)
4. [Metadata with Restricted Options](#metadata-with-restricted-options)
5. [Update Examples](#update-examples)
6. [Common Patterns](#common-patterns)

---

## Introduction

Fixed metadata (also called DEFAULT metadata, `type = 1`) are predefined system fields that come with every contract. These fields have specific data types and some have restricted value options. All fixed metadata can be updated using the same endpoint, but the format and validation rules vary by field type.

### Key Concepts

- **Fixed Metadata**: System-defined metadata fields (cannot be created/deleted)
- **MetaKey ID**: Unique identifier for each metadata field (1-20)
- **MetaKey Label**: System label used internally (e.g., "title", "conpass_person")
- **Data Types**: Text, Date, Person (multi-select), Contract Type (restricted options)

---

## Metadata Update Endpoint

### Endpoint Details

- **URL**: `PUT /contract/<contract_id>/metadata`
- **Method**: `PUT`
- **URL Parameter**: `contract_id` (integer, required) - The ID of the contract
- **Content-Type**: `application/json`
- **Authentication**: JWT token in HTTP-only cookie (set by `JWT_AUTH_COOKIE` setting)

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

| Field       | Type    | Required | Description                 | Constraints                                          |
| ----------- | ------- | -------- | --------------------------- | ---------------------------------------------------- |
| `id`        | integer | **Yes**  | Existing metadata record ID | Must exist, belong to contract, and be ENABLE status |
| `value`     | string  | No       | New text value              | Max 255 characters. Ignored if `lock: true`          |
| `dateValue` | date    | No       | New date value              | Format: `YYYY-MM-DD`. Ignored if `lock: true`        |
| `lock`      | boolean | No       | Lock/unlock status          | Can be changed even when metadata is locked          |

### Important Notes

- **Lock Status**: When `metadata.lock == true`, `value` and `dateValue` updates are silently ignored. Only `lock` can be changed.
- **To update locked metadata**: First unlock (`{"id": 123, "lock": false}`), then update the value.
- **Batch Operations**: Multiple metadata items can be updated in a single request.

---

## Fixed Metadata Types

All fixed metadata fields are listed below with their MetaKey IDs, labels, names, and data types.

### Text Fields

These fields accept plain text values (max 255 characters).

#### 1. Contract Title (契約書名)

- **MetaKey ID**: `1`
- **Label**: `title`
- **Data Type**: Text
- **Special Behavior**: Updating this field automatically updates `contract.name`
- **Update Format**: `{"id": <metadata_id>, "value": "Contract Title"}`

#### 2. Company Name (甲) - 会社名（甲）

- **MetaKey ID**: `2`
- **Label**: `companya`
- **Data Type**: Text
- **Update Format**: `{"id": <metadata_id>, "value": "Company A Name"}`

#### 3. Company Name (乙) - 会社名（乙）

- **MetaKey ID**: `3`
- **Label**: `companyb`
- **Data Type**: Text
- **Update Format**: `{"id": <metadata_id>, "value": "Company B Name"}`

#### 4. Company Name (丙) - 会社名（丙）

- **MetaKey ID**: `4`
- **Label**: `companyc`
- **Data Type**: Text
- **Update Format**: `{"id": <metadata_id>, "value": "Company C Name"}`

#### 5. Company Name (丁) - 会社名（丁）

- **MetaKey ID**: `5`
- **Label**: `companyd`
- **Data Type**: Text
- **Update Format**: `{"id": <metadata_id>, "value": "Company D Name"}`

#### 6. Document ID (管理番号)

- **MetaKey ID**: `11`
- **Label**: `docid`
- **Data Type**: Text
- **Update Format**: `{"id": <metadata_id>, "value": "DOC-12345"}`

#### 7. Related Contract (関連契約書)

- **MetaKey ID**: `12`
- **Label**: `related_contract`
- **Data Type**: Text
- **Update Format**: `{"id": <metadata_id>, "value": "Related Contract Reference"}`

#### 8. Court (裁判所)

- **MetaKey ID**: `14`
- **Label**: `cort`
- **Data Type**: Text
- **Update Format**: `{"id": <metadata_id>, "value": "Tokyo District Court"}`

#### 9. Auto Update (自動更新の有無)

- **MetaKey ID**: `9`
- **Label**: `autoupdate`
- **Data Type**: Text
- **Update Format**: `{"id": <metadata_id>, "value": "Yes"}` or `{"id": <metadata_id>, "value": "No"}`

#### 10. Outsource Prohibition (再委託禁止)

- **MetaKey ID**: `15`
- **Label**: `outsource`
- **Data Type**: Text
- **Status**: May be disabled (status = 0) in some installations
- **Update Format**: `{"id": <metadata_id>, "value": "Prohibited"}`

#### 11. Contract Renewal Notification (契約更新通知)

- **MetaKey ID**: `18`
- **Label**: `conpass_contract_renew_notify`
- **Data Type**: Text
- **Update Format**: `{"id": <metadata_id>, "value": "Notification text"}`

#### 12. Amount (金額)

- **MetaKey ID**: `19`
- **Label**: `conpass_amount`
- **Data Type**: Text
- **Update Format**: `{"id": <metadata_id>, "value": "1000000"}`

#### 13. Anti-Social Clause (反社条項の有無)

- **MetaKey ID**: `20`
- **Label**: `antisocial`
- **Data Type**: Text
- **Update Format**: `{"id": <metadata_id>, "value": "Yes"}` or `{"id": <metadata_id>, "value": "No"}`

### Date Fields

These fields accept date values in `YYYY-MM-DD` format.

#### 14. Contract Date (契約日)

- **MetaKey ID**: `6`
- **Label**: `contractdate`
- **Data Type**: Date
- **Update Format**: `{"id": <metadata_id>, "dateValue": "2024-01-15"}`

#### 15. Contract Start Date (契約開始日)

- **MetaKey ID**: `7`
- **Label**: `contractstartdate`
- **Data Type**: Date
- **Update Format**: `{"id": <metadata_id>, "dateValue": "2024-01-01"}`

#### 16. Contract End Date (契約終了日)

- **MetaKey ID**: `8`
- **Label**: `contractenddate`
- **Data Type**: Date
- **Update Format**: `{"id": <metadata_id>, "dateValue": "2024-12-31"}`

#### 17. Cancellation Notice Date (解約ノーティス日)

- **MetaKey ID**: `10`
- **Label**: `cancelnotice`
- **Data Type**: Date
- **Update Format**: `{"id": <metadata_id>, "dateValue": "2024-11-30"}`

#### 18. Related Contract Date (関連契約日)

- **MetaKey ID**: `13`
- **Label**: `related_contract_date`
- **Data Type**: Date
- **Update Format**: `{"id": <metadata_id>, "dateValue": "2024-01-10"}`

---

## Metadata with Restricted Options

Some metadata fields have restricted value options. You must use one of the predefined values.

### 1. Contract Type (契約種別) - `conpass_contract_type`

**MetaKey ID**: `16`  
**Label**: `conpass_contract_type`  
**Data Type**: Text (restricted options)

#### Available Options

The contract type metadata accepts one of the following predefined values:

| Type ID | Name (Japanese)  | Name (English)                 |
| ------- | ---------------- | ------------------------------ |
| 1       | 秘密保持契約書   | Non-Disclosure Agreement       |
| 2       | 雇用契約書       | Employment Contract            |
| 3       | 申込注文書       | Order Form                     |
| 4       | 業務委託契約書   | Service Agreement              |
| 5       | 売買契約書       | Sales Contract                 |
| 6       | 請負契約書       | Construction Contract          |
| 7       | 賃貸借契約書     | Lease Agreement                |
| 8       | 派遣契約書       | Dispatch Contract              |
| 9       | 金銭消費貸借契約 | Loan Agreement                 |
| 10      | 代理店契約書     | Agency Agreement               |
| 11      | 業務提携契約書   | Business Partnership Agreement |
| 12      | ライセンス契約書 | License Agreement              |
| 13      | 顧問契約書       | Advisory Agreement             |
| 14      | 譲渡契約書       | Transfer Agreement             |
| 15      | 和解契約書       | Settlement Agreement           |
| 16      | 誓約書           | Pledge                         |
| 17      | その他           | Other                          |

**Note**: The system also accepts type ID `18` as a default fallback value, but it's not in the standard list.

#### How to Get Options

The contract type options are hardcoded in the system. You can reference them from the codebase or use the values listed above. There is no API endpoint to retrieve these options dynamically.

#### Update Format

```json
{
  "params": {
    "list": [
      {
        "id": <metadata_id>,
        "value": "秘密保持契約書"
      }
    ]
  }
}
```

**Important**: You must use the exact Japanese name as shown in the table above. The system matches by name, not by type ID.

### 2. Person in Charge (担当者名) - `conpass_person`

**MetaKey ID**: `17`  
**Label**: `conpass_person`  
**Data Type**: Multi-select (comma-separated user IDs)

#### Special Behavior

- **Multiple Values**: This field supports multiple persons assigned to a contract
- **Format**: Comma-separated user IDs (e.g., `"1,2,3"`)
- **Storage**: Each person ID is stored as a separate `MetaData` record with the same `key`
- **Automatic Management**: The system automatically:
  - **Adds**: Person IDs in new value but not in existing records
  - **Deletes**: Person IDs in existing records but not in new value
  - **Updates**: Person IDs present in both (updates timestamp)

#### How to Get Available Persons

**Endpoint**: `GET /user/list` or `GET /user/data/list`

**Request Headers**:

- Cookie: JWT authentication token

**Query Parameters** (optional):

- `userName` (string): Filter by username (partial match)

**Response Format**:

```json
[
  {
    "id": 1,
    "loginName": "user@example.com",
    "username": "John Doe",
    "email": "user@example.com",
    "type": 1,
    "status": 1
  },
  {
    "id": 2,
    "loginName": "user2@example.com",
    "username": "Jane Smith",
    "email": "user2@example.com",
    "type": 1,
    "status": 1
  }
]
```

**Response Fields**:

- `id` (integer): User ID - **Use this as the person ID in metadata**
- `loginName` (string): Login email
- `username` (string): Display name
- `email` (string): Email address
- `type` (integer): User type (1 = ACCOUNT, 2 = CLIENT, etc.)
- `status` (integer): 1 = ENABLE, 0 = DISABLE

**Notes**:

- Only returns users from the authenticated user's account
- Only returns ENABLE status users (`status = 1`)
- Only returns ACCOUNT type users (`type = 1`)
- Excludes BPO users (`is_bpo = false`)

#### Update Format

```json
{
  "params": {
    "list": [
      {
        "id": <metadata_id>,
        "value": "1,2,3"
      }
    ]
  }
}
```

**Example Scenario**:

**Current State**: Persons `[1, 4]` are assigned

**Request**:

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

- Person `1`: Updated (timestamp refreshed)
- Person `2`: Created (new record)
- Person `3`: Created (new record)
- Person `4`: Deleted (removed from contract)

**Important Notes**:

- Always provide the **complete list** of person IDs (not just additions)
- The system calculates the difference and adds/removes accordingly
- Person IDs must be valid user IDs from the account
- Empty string `""` removes all persons
- Locked metadata: Person updates are ignored if `lock: true`, just like regular metadata

---

## Update Examples

### Example 1: Update Text Field

Update the contract title:

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

**Result**:

- Metadata value updated
- `Contract.name` automatically updated to "New Contract Title"

### Example 2: Update Date Field

Update the contract end date:

```json
{
  "params": {
    "list": [
      {
        "id": 101,
        "dateValue": "2024-12-31"
      }
    ]
  }
}
```

### Example 3: Update Contract Type

Update the contract type to "業務委託契約書":

```json
{
  "params": {
    "list": [
      {
        "id": 102,
        "value": "業務委託契約書"
      }
    ]
  }
}
```

### Example 4: Update Person Metadata

Assign persons with IDs 1, 2, and 3:

```json
{
  "params": {
    "list": [
      {
        "id": 103,
        "value": "1,2,3"
      }
    ]
  }
}
```

### Example 5: Batch Update Multiple Fields

Update multiple metadata fields in one request:

```json
{
  "params": {
    "list": [
      {
        "id": 100,
        "value": "Updated Contract Title"
      },
      {
        "id": 101,
        "dateValue": "2024-12-31"
      },
      {
        "id": 102,
        "value": "業務委託契約書"
      },
      {
        "id": 103,
        "value": "1,2,3"
      }
    ]
  }
}
```

### Example 6: Unlock and Update Locked Metadata

If metadata is locked, unlock it first, then update:

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

### Example 7: Remove All Persons

To remove all assigned persons:

```json
{
  "params": {
    "list": [
      {
        "id": 103,
        "value": ""
      }
    ]
  }
}
```

---

## Common Patterns

### Pattern 1: Get Current Metadata Before Update

**Step 1**: Get current metadata to find the metadata ID:

```http
GET /contract/123/metadata
Cookie: auth-token=<jwt_token>
```

**Step 2**: Find the metadata item you want to update from the response:

```json
[
  {
    "id": 100,
    "key": {
      "id": 1,
      "name": "契約書名",
      "label": "title"
    },
    "value": "Current Title",
    "lock": false
  }
]
```

**Step 3**: Use the `id` from the response to update:

```json
{
  "params": {
    "list": [
      {
        "id": 100,
        "value": "Updated Title"
      }
    ]
  }
}
```

### Pattern 2: Get Available Persons Before Assigning

**Step 1**: Get list of available users:

```http
GET /user/list
Cookie: auth-token=<jwt_token>
```

**Step 2**: Extract user IDs from response:

```json
[
  { "id": 1, "username": "John Doe" },
  { "id": 2, "username": "Jane Smith" },
  { "id": 3, "username": "Bob Wilson" }
]
```

**Step 3**: Use the IDs in person metadata update:

```json
{
  "params": {
    "list": [
      {
        "id": 103,
        "value": "1,2,3"
      }
    ]
  }
}
```

### Pattern 3: Handle Locked Metadata

**Check if metadata is locked**:

```json
{
  "id": 200,
  "lock": true, // ← Check this field
  "value": "Current value"
}
```

**If locked and you need to update**:

1. First unlock: `{"id": 200, "lock": false}`
2. Then update: `{"id": 200, "value": "New value"}`

### Pattern 4: Validate Contract Type Value

Before updating contract type, ensure the value matches one of the predefined options:

- ✅ Valid: `"秘密保持契約書"`, `"業務委託契約書"`, `"その他"`
- ❌ Invalid: `"NDA"`, `"Service Agreement"`, `"Custom Type"`

Use the exact Japanese name from the contract type options table.

---

## Summary Table

| MetaKey ID | Label                         | Name (Japanese)  | Data Type          | Special Behavior         |
| ---------- | ----------------------------- | ---------------- | ------------------ | ------------------------ |
| 1          | title                         | 契約書名         | Text               | Updates contract.name    |
| 2          | companya                      | 会社名（甲）     | Text               | -                        |
| 3          | companyb                      | 会社名（乙）     | Text               | -                        |
| 4          | companyc                      | 会社名（丙）     | Text               | -                        |
| 5          | companyd                      | 会社名（丁）     | Text               | -                        |
| 6          | contractdate                  | 契約日           | Date               | -                        |
| 7          | contractstartdate             | 契約開始日       | Date               | -                        |
| 8          | contractenddate               | 契約終了日       | Date               | -                        |
| 9          | autoupdate                    | 自動更新の有無   | Text               | -                        |
| 10         | cancelnotice                  | 解約ノーティス日 | Date               | -                        |
| 11         | docid                         | 管理番号         | Text               | -                        |
| 12         | related_contract              | 関連契約書       | Text               | -                        |
| 13         | related_contract_date         | 関連契約日       | Date               | -                        |
| 14         | cort                          | 裁判所           | Text               | -                        |
| 15         | outsource                     | 再委託禁止       | Text               | May be disabled          |
| 16         | conpass_contract_type         | 契約種別         | Text (restricted)  | 17 predefined options    |
| 17         | conpass_person                | 担当者名         | Multi-select (IDs) | Comma-separated user IDs |
| 18         | conpass_contract_renew_notify | 契約更新通知     | Text               | -                        |
| 19         | conpass_amount                | 金額             | Text               | -                        |
| 20         | antisocial                    | 反社条項の有無   | Text               | -                        |

---

## Error Handling

### Common Errors

1. **Metadata Not Found** (`400 Bad Request`):

   ```json
   {
     "msg": "パラメータが不正です"
   }
   ```

   **Cause**: Metadata ID doesn't exist, belongs to different contract, or has `status = DISABLE`

2. **Invalid Date Format**:

   - Use `YYYY-MM-DD` format
   - Example: `"2024-01-15"` ✅, `"01/15/2024"` ❌

3. **Value Too Long**:

   - Text values limited to 255 characters
   - Truncate if necessary

4. **Invalid Contract Type**:

   - Must use exact Japanese name from options table
   - Case-sensitive

5. **Invalid Person ID**:

   - Person IDs must be valid user IDs from the account
   - Use `GET /user/list` to get valid IDs

6. **Locked Metadata**:
   - Updates to `value` and `dateValue` are silently ignored
   - Unlock first, then update

---

## Best Practices

1. **Always get current metadata first** to verify IDs and lock status
2. **Validate values before updating** (especially contract type and person IDs)
3. **Use batch operations** when updating multiple fields
4. **Check lock status** before attempting value updates
5. **For person metadata**, always provide the complete list (not just additions)
6. **For contract type**, use exact Japanese names from the options table
7. **Handle errors gracefully** and provide meaningful error messages

---

**Last Updated**: Based on codebase analysis of `app/conpass/views/contract/views.py`, `app/conpass/models/constants/contractmetakeyidable.py`, and `app/conpass/services/growth_verse/gv_prediction.py`  
**Version**: 1.0
