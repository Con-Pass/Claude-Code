# Contract Body API Documentation

## Overview

This document describes the API endpoint for retrieving the full contract body text from the ConPass backend system.

## API Endpoint

**Endpoint:** `GET /contract/body`

**URL Pattern:** `/contract/body`

**View Class:** `BodyView` (located in `app/conpass/views/contract/views.py`)

## Description

Retrieves the full body text of a contract. The API returns the latest enabled version of the contract body by default, or a specific version if requested. The contract must belong to the authenticated user's account.

## Request Parameters

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | Integer | Yes | The contract ID |
| `version` | String | No | The specific version to retrieve. If omitted, returns the latest version |

### Request Serializer

The request is validated using `ContractBodyItemRequestBodySerializer`:

```python
class ContractBodyItemRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()  # Required: Contract ID
    version = serializers.CharField(required=False)  # Optional: Version string
    body = serializers.CharField(required=False)  # Not used for GET requests
    isProvider = serializers.IntegerField(required=False, default=None)
    comment = serializers.CharField(required=False, allow_blank=True)
```

## Authentication

**Required:** Yes

The API requires user authentication. The endpoint automatically filters contracts based on the authenticated user's `account_id`. Only contracts belonging to the user's account can be accessed.

## Request Examples

### Get Latest Version

```bash
GET /contract/body?id=123
```

**cURL Example:**
```bash
curl -X GET "https://your-api-domain.com/contract/body?id=123" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

### Get Specific Version

```bash
GET /contract/body?id=123&version=1.0
```

**cURL Example:**
```bash
curl -X GET "https://your-api-domain.com/contract/body?id=123&version=1.0" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

## Response Format

### Success Response (200 OK)

The response contains a nested structure with the contract body information:

```json
{
  "response": {
    "id": 789,
    "contract": {
      "id": 123,
      "name": "契約書名",
      "type": 1,
      "account_id": 456,
      "client_id": 789,
      "directory": {
        "id": 1,
        "name": "ディレクトリ名",
        // ... other directory fields
      },
      "template_id": null,
      "origin_id": null,
      "version": "1.0",
      "files": [
        // ... file objects
      ],
      "isGarbage": false,
      "isProvider": true,
      "status": 1,
      "createdAt": "2024-01-01 12:00:00",
      "createdBy": {
        "id": 1,
        "name": "User Name",
        // ... other user fields
      },
      "updatedAt": "2024-01-01 12:00:00",
      "updatedBy": {
        "id": 1,
        "name": "User Name",
        // ... other user fields
      }
    },
    "version": "1.0",
    "isAdopted": true,
    "body": "%E5%A5%91%E7%B4%84%E6%9B%B8%E3%81%AE%E6%9C%AC%E6%96%87%E3%83%86%E3%82%AD%E3%82%B9%E3%83%88%EF%BC%88%E3%81%93%E3%82%8C%E3%81%8C%E3%83%95%E3%83%AB%E3%83%86%E3%82%AD%E3%82%B9%E3%83%88%EF%BC%89",  // URL-encoded: "契約書の本文テキスト（これがフルテキスト）"
    "status": 1,
    "createdAt": "2024-01-01 12:00:00",
    "createdBy": {
      "id": 1,
      "name": "User Name",
      // ... other user fields
    },
    "updatedAt": "2024-01-01 12:00:00",
    "updatedBy": {
      "id": 1,
      "name": "User Name",
      // ... other user fields
    }
  }
}
```

### Response Fields

#### Top Level
- `response` (Object): Contains the contract body data

#### Response Object Fields
- `id` (Integer): Contract body ID
- `contract` (Object): Full contract details object
  - `id` (Integer): Contract ID
  - `name` (String): Contract name
  - `type` (Integer): Contract type (1: normal, 2: template, 3: past contract)
  - `account_id` (Integer, nullable): Account ID
  - `client_id` (Integer, nullable): Client ID
  - `directory` (Object, nullable): Directory information
  - `template_id` (Integer, nullable): Template ID
  - `origin_id` (Integer, nullable): Origin contract ID
  - `version` (String): Contract version
  - `files` (Array): Linked files
  - `isGarbage` (Boolean): Whether contract is in trash
  - `isProvider` (Boolean): Whether it's the provider's contract
  - `status` (Integer): Contract status (1: enabled, 0: disabled)
  - `createdAt` (String): Creation timestamp (format: "YYYY-MM-DD HH:MM:SS")
  - `createdBy` (Object): Creator user information
  - `updatedAt` (String): Update timestamp (format: "YYYY-MM-DD HH:MM:SS")
  - `updatedBy` (Object): Updater user information
- `version` (String): Contract body version
- `isAdopted` (Boolean): Whether this version is adopted
- **`body` (String): The full contract body text** ⭐ This is the main field you need
  - **⚠️ IMPORTANT: The body text is URL-encoded in the response**
  - You need to URL-decode it to get the actual text: `urllib.parse.unquote(body)` (Python) or `decodeURIComponent(body)` (JavaScript)
  - Example: `"Hello%20World"` → `"Hello World"`
- `status` (Integer): Contract body status (1: enabled, 0: disabled)
- `createdAt` (String): Creation timestamp (format: "YYYY-MM-DD HH:MM:SS")
- `createdBy` (Object): Creator user information
- `updatedAt` (String): Update timestamp (format: "YYYY-MM-DD HH:MM:SS")
- `updatedBy` (Object): Updater user information

### Error Responses

#### 400 Bad Request

**Contract Not Found:**
```json
"契約書が見つかりません"
```

This error occurs when:
- The contract ID doesn't exist
- The contract doesn't belong to the user's account
- The contract status is DISABLE
- The contract body version doesn't exist

**Validation Error:**
```json
{
  "id": ["This field is required."]
}
```

This occurs when required parameters are missing or invalid.

## Implementation Details

### View Class Location
- **File:** `app/conpass/views/contract/views.py`
- **Class:** `BodyView` (lines 449-490)
- **Method:** `get(self, request)`

### Serializer Classes
- **Request Serializer:** `ContractBodyItemRequestBodySerializer`
  - Location: `app/conpass/views/contract/serializer/contract_body_serializer.py`
- **Response Serializer:** `ContractBodyItemResponseBodySerializer`
  - Location: `app/conpass/views/contract/serializer/contract_body_serializer.py`

### Business Logic

1. **Validation:** Request parameters are validated using the request serializer
2. **Account Check:** Verifies the contract belongs to the authenticated user's account
3. **Status Filter:** Only retrieves contracts with status != DISABLE
4. **Version Selection:**
   - If `version` is provided: Returns the specific version
   - If `version` is not provided: Returns the latest version based on `updated_at`
5. **Status Filter:** Only retrieves contract bodies with status = ENABLE
6. **Latest Selection:** Uses `.latest('updated_at')` to get the most recent version

### Database Models

- **Contract Model:** `app/conpass/models/contract.py`
- **ContractBody Model:** `app/conpass/models/contract_body.py`

## Usage Examples

### JavaScript/TypeScript (Fetch API)

```javascript
async function getContractBody(contractId, version = null) {
  const url = new URL('/contract/body', 'https://your-api-domain.com');
  url.searchParams.append('id', contractId);
  if (version) {
    url.searchParams.append('version', version);
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${yourAuthToken}`,
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const data = await response.json();
  // Decode URL-encoded body text
  return decodeURIComponent(data.response.body); // Full contract body text (decoded)
}

// Usage
const bodyText = await getContractBody(123);
console.log(bodyText);
```

### Python (requests)

```python
import requests

def get_contract_body(contract_id, version=None, auth_token=None):
    url = "https://your-api-domain.com/contract/body"
    params = {"id": contract_id}
    
    if version:
        params["version"] = version
    
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    # Decode URL-encoded body text
    import urllib.parse
    return urllib.parse.unquote(data["response"]["body"])  # Full contract body text (decoded)

# Usage
body_text = get_contract_body(123, auth_token="your_token")
print(body_text)
```

---

# Contract Body List API Documentation

## Overview

This document describes the API endpoint for retrieving a list of all contract body versions with diff information.

## API Endpoint

**Endpoint:** `GET /contract/body/list`

**URL Pattern:** `/contract/body/list`

**View Class:** `ContractBodyListView` (located in `app/conpass/views/contract/views.py`)

## Description

Retrieves a list of all enabled contract body versions for a specific contract, ordered by update time (newest first). Each version includes diff information showing what was added or removed compared to the previous version. The full contract body object is also included for each version.

## Request Parameters

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | Integer | Yes | The contract ID |

### Request Serializer

The request is validated using `ContractBodyListRequestBodySerializer`:

```python
class ContractBodyListRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField()  # Required: Contract ID
```

## Authentication

**Required:** Yes

The API requires user authentication. The endpoint automatically filters contracts based on the authenticated user's `account_id`. Only contracts belonging to the user's account can be accessed.

## Request Examples

### Get All Versions

```bash
GET /contract/body/list?id=123
```

**cURL Example:**
```bash
curl -X GET "https://your-api-domain.com/contract/body/list?id=123" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

## Response Format

### Success Response (200 OK)

The response contains a list of contract body versions with diff information:

```json
{
  "response": [
    {
      "diff": "%EF%BC%88%E8%BF%BD%E5%8A%A0%EF%BC%89New%20text%20added",  // URL-encoded diff
      "body": {
        "id": 789,
        "contract": {
          "id": 123,
          "name": "契約書名",
          // ... full contract object
        },
        "version": "2.0",
        "isAdopted": true,
        "body": "%E5%A5%91%E7%B4%84%E6%9B%B8%E3%81%AE%E6%9C%AC%E6%96%87...",  // URL-encoded
        "status": 1,
        "createdAt": "2024-01-02 12:00:00",
        "createdBy": { /* user info */ },
        "updatedAt": "2024-01-02 12:00:00",
        "updatedBy": { /* user info */ }
      }
    },
    {
      "diff": "%EF%BC%88%E5%89%8A%E9%99%A4%EF%BC%89Old%20text%20removed",  // URL-encoded diff
      "body": {
        "id": 788,
        "contract": { /* ... */ },
        "version": "1.0",
        "isAdopted": false,
        "body": "%E5%A5%91%E7%B4%84%E6%9B%B8%E3%81%AE%E6%9C%AC%E6%96%87...",  // URL-encoded
        "status": 1,
        "createdAt": "2024-01-01 12:00:00",
        "createdBy": { /* user info */ },
        "updatedAt": "2024-01-01 12:00:00",
        "updatedBy": { /* user info */ }
      }
    }
  ]
}
```

### Response Fields

#### Top Level
- `response` (Array): List of contract body versions with diff information

#### Each Item in Response Array
- `diff` (String): **URL-encoded** diff text showing changes from previous version
  - Format: `"（追加）"` (added) or `"（削除）"` (removed) followed by the changed text
  - Contains only additions and deletions, not the full text
  - Must be URL-decoded before use
- `body` (Object): Full contract body object (same structure as `/contract/body` response)
  - `id` (Integer): Contract body ID
  - `contract` (Object): Full contract details
  - `version` (String): Version string
  - `isAdopted` (Boolean): Whether this version is adopted
  - **`body` (String): The full contract body text (URL-encoded)** ⚠️
  - `status` (Integer): Status
  - `createdAt` (String): Creation timestamp
  - `createdBy` (Object): Creator user information
  - `updatedAt` (String): Update timestamp
  - `updatedBy` (Object): Updater user information

### Error Responses

#### 400 Bad Request

**Validation Error:**
```json
{
  "id": ["This field is required."]
}
```

This occurs when the `id` parameter is missing or invalid.

## Implementation Details

### View Class Location
- **File:** `app/conpass/views/contract/views.py`
- **Class:** `ContractBodyListView` (lines 529-576)
- **Method:** `get(self, request)`

### Serializer Classes
- **Request Serializer:** `ContractBodyListRequestBodySerializer`
  - Location: `app/conpass/views/contract/serializer/contract_body_serializer.py`
- **Response Serializer:** `ContractBodyListResponseBodySerializer`
  - Location: `app/conpass/views/contract/serializer/contract_body_serializer.py`

### Business Logic

1. **Validation:** Request parameters are validated using the request serializer
2. **Account Check:** Automatically filters by authenticated user's account
3. **Status Filter:** Only retrieves contract bodies with status = ENABLE
4. **Ordering:** Results are ordered by `updated_at` (oldest first initially)
5. **Diff Calculation:** 
   - Compares each version with the previous one
   - Extracts only additions (`+`) and deletions (`-`)
   - Marks additions with `"（追加）"` (added) prefix
   - Marks deletions with `"（削除）"` (removed) prefix
   - Filters out `&nbsp;` entities
6. **Reversal:** Results are reversed to show newest versions first
7. **Encoding:** Both `diff` and `body.body` fields are URL-encoded

### Diff Algorithm

The diff is calculated using Python's `difflib.ndiff()`:
- Compares line-by-line between previous and current version
- Only includes lines that were added (`+`) or removed (`-`)
- Excludes unchanged lines and `&nbsp;` entities
- The diff text is URL-encoded before being returned

## Usage Examples

### JavaScript/TypeScript (Fetch API)

```javascript
async function getContractBodyList(contractId) {
  const url = new URL('/contract/body/list', 'https://your-api-domain.com');
  url.searchParams.append('id', contractId);

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${yourAuthToken}`,
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const data = await response.json();
  
  // Process each version
  return data.response.map(item => ({
    diff: decodeURIComponent(item.diff),  // Decode diff
    body: {
      ...item.body,
      body: decodeURIComponent(item.body.body)  // Decode body text
    }
  }));
}

// Usage
const versions = await getContractBodyList(123);
versions.forEach(version => {
  console.log(`Version ${version.body.version}:`);
  console.log(`Diff: ${version.diff}`);
  console.log(`Body: ${version.body.body}`);
});
```

### Python (requests)

```python
import requests
import urllib.parse

def get_contract_body_list(contract_id, auth_token=None):
    url = "https://your-api-domain.com/contract/body/list"
    params = {"id": contract_id}
    
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    
    # Decode both diff and body text
    decoded_versions = []
    for item in data["response"]:
        decoded_versions.append({
            "diff": urllib.parse.unquote(item["diff"]),
            "body": {
                **item["body"],
                "body": urllib.parse.unquote(item["body"]["body"])
            }
        })
    
    return decoded_versions

# Usage
versions = get_contract_body_list(123, auth_token="your_token")
for version in versions:
    print(f"Version {version['body']['version']}:")
    print(f"Diff: {version['diff']}")
    print(f"Body: {version['body']['body']}")
```

## Encoding Information

### ⚠️ Important: URL Encoding

**Both the `diff` and `body.body` fields are URL-encoded** in the response.

#### Fields that need decoding:
1. **`diff`** - The diff text showing changes
2. **`body.body`** - The full contract body text

#### How to decode:

**Python:**
```python
import urllib.parse

# Decode diff
diff_decoded = urllib.parse.unquote(item["diff"])

# Decode body text
body_decoded = urllib.parse.unquote(item["body"]["body"])
```

**JavaScript/TypeScript:**
```javascript
// Decode diff
const diffDecoded = decodeURIComponent(item.diff);

// Decode body text
const bodyDecoded = decodeURIComponent(item.body.body);
```

## Notes

- **Order:** Versions are returned in reverse chronological order (newest first)
- **Diff Content:** The diff only contains additions and deletions, not the full text
- **Diff Format:** 
  - Additions are prefixed with `"（追加）"` (added)
  - Deletions are prefixed with `"（削除）"` (removed)
- **Encoding:** Both `diff` and `body.body` are URL-encoded and must be decoded
- **Full Body:** Each item includes the complete contract body object, so you have access to the full text if needed
- Only enabled contract bodies (status = ENABLE) are returned
- The API automatically filters by the authenticated user's account

## URL Configuration

The endpoint is registered in `app/conpass/urls.py` at line 113:

```python
path('contract/body/list', ContractBodyListView.as_view()),
```

---

## Related Endpoints

- **GET /contract/body** - Get a single contract body version (documented above)
- **POST /contract/body/add** - Save a new contract body version
- **GET /contract/body/diff** - Get HTML diff between two contract body versions
- **POST /contract/body/version/adopt** - Adopt a specific version as the current version

## Encoding Information

### ⚠️ Important: URL Encoding

**The contract body text in the response is URL-encoded.** You must decode it before use.

#### How it's stored:
- The body is stored in the database as **URL-encoded** text (using `urllib.parse.quote()`)
- When retrieved via GET `/contract/body`, it's returned **as-is** (URL-encoded)
- No automatic decoding is performed by the API

#### How to decode:

**Python:**
```python
import urllib.parse

# After getting the response
body_encoded = data["response"]["body"]
body_decoded = urllib.parse.unquote(body_encoded)
```

**JavaScript/TypeScript:**
```javascript
// After getting the response
const bodyEncoded = data.response.body;
const bodyDecoded = decodeURIComponent(bodyEncoded);
```

**cURL/Command Line:**
```bash
# Use a tool like Python or Node.js to decode
python -c "import urllib.parse; print(urllib.parse.unquote('$ENCODED_TEXT'))"
```

#### Example:
- **Encoded:** `"Hello%20World%21%3C%2Fp%3E"`
- **Decoded:** `"Hello World!</p>"`

## Notes

- The contract body text is stored in the `body` field of the response
- **The body text is URL-encoded** - you must decode it before displaying or processing
- Multiple versions of a contract body can exist; use the `version` parameter to retrieve a specific version
- Only enabled contract bodies (status = ENABLE) are returned
- The API automatically filters by the authenticated user's account
- Timestamps are returned in the format: "YYYY-MM-DD HH:MM:SS"
- The `isAdopted` field indicates whether this version is the currently adopted version

## URL Configuration

The endpoint is registered in `app/conpass/urls.py` at line 111:

```python
path('contract/body', contractBodyItemView.as_view()),  # get
```

Where `contractBodyItemView` is imported as:
```python
from conpass.views.contract.views import BodyView as contractBodyItemView
```
