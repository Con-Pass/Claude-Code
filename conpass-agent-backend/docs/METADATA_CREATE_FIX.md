# Metadata CREATE Operation Fix

## Problem

When using the agent to update metadata for fields that have no value yet (`id: null`), the agent would report an error:

```
"The company C metadata currently has no metadata_id, so it cannot be updated directly."
```

The dashboard was able to update these fields successfully by using `key_id` instead of `id` in the request payload.

## Root Cause

The system had three issues:

1. **Schema Limitation**: `MetadataUpdateItem` only accepted `metadata_id`, not `key_id`
2. **Processing Logic**: The `update_metadata` function skipped metadata items with `id: null` 
3. **API Endpoint**: The execution API only handled `metadata_id`, not `key_id`

## Solution

### 1. Updated Schema (`app/schemas/metadata_crud.py`)

**Changed `MetadataUpdateItem`** to accept both `metadata_id` and `key_id`:

```python
class MetadataUpdateItem(BaseModel):
    metadata_id: Optional[int] = None  # For UPDATE operations
    key_id: Optional[int] = None       # For CREATE operations
    value: Optional[str] = None
    date_value: Optional[str] = None
    lock: Optional[bool] = None
```

- Added validator to ensure only one of `metadata_id` or `key_id` is provided
- Updated `UpdateMetadataAction` validator to allow items with `key_id`

### 2. Updated Processing Logic (`app/services/chatbot/tools/metadata_crud/update_metadata.py`)

**Built dual mapping system** for metadata:

```python
current_metadata_map = {}  # Map by metadata_id (for UPDATE)
key_metadata_map = {}      # Map by key_id (for all records)
```

**Added support for CREATE operations**:

- When `metadata_id` is provided → UPDATE existing metadata
- When `key_id` is provided → CREATE new metadata value
- Validates that key with `id: null` doesn't already have a metadata record

### 3. Updated Read Tool (`app/services/chatbot/tools/metadata_crud/read_metadata.py`)

**Added `key_id` to response**:

```python
extracted_metadata.append({
    "metadata_id": metadata_id,
    "key_id": key_id,          # NEW: Added key.id
    "key_name": key_name,
    "key_label": key_label,
    "value": value,
    "date_value": date_value,
    "is_locked": is_locked,
})
```

Now the agent can see both `metadata_id` (for UPDATE) and `key_id` (for CREATE).

### 4. Updated API Endpoint (`app/api/v1/metadata_crud.py`)

**Modified `/metadata/update` to handle both operations**:

```python
if item.metadata_id is not None:
    # UPDATE existing metadata
    api_item["id"] = item.metadata_id
elif item.key_id is not None:
    # CREATE new metadata value
    api_item["key_id"] = item.key_id
```

### 5. Updated Tool Descriptions (`app/services/chatbot/tools/metadata_crud/metadata_crud_tools.py`)

**Updated `read_metadata` description**:
- Now mentions it returns both `metadata_id` and `key_id`

**Updated `update_metadata` description**:
- Clarifies it supports both UPDATE (with `metadata_id`) and CREATE (with `key_id`)
- Explains when to use each operation

### 6. Updated Documentation (`docs/METADATA_UPDATE_GUIDE.md`)

Added comprehensive section explaining:
- UPDATE vs CREATE operations
- When to use `id` vs `key_id`
- Mixed batch operations example
- Field requirements for each operation type

## How It Works Now

### Example Scenario: Setting Company C Value

**1. Agent reads metadata:**

```json
{
  "metadata_id": null,
  "key_id": 4,
  "key_name": "会社名（丙）",
  "key_label": "companyc",
  "value": "",
  "is_locked": false
}
```

**2. Agent calls `update_metadata` with `key_id`:**

```python
update_metadata(
    contract_id=123,
    updates=[
        {
            "key_id": 4,  # Use key_id since metadata_id is null
            "value": "New Company C"
        }
    ]
)
```

**3. System processes CREATE operation:**

- Looks up metadata by `key_id=4` in `key_metadata_map`
- Validates that it has no existing metadata record (`metadata_id is null`)
- Creates `MetadataItem` with `key_id=4` (not `metadata_id`)
- Returns `UpdateMetadataAction` for user approval

**4. User approves, API executes:**

```json
{
  "params": {
    "list": [
      {
        "key_id": 4,
        "value": "New Company C"
      }
    ]
  }
}
```

**5. ConPass API creates new metadata record:**

- New record is created with auto-generated ID (e.g., 90876)
- Future updates use `id: 90876` instead of `key_id: 4`

## Benefits

1. **Parity with Dashboard**: Agent can now do everything the dashboard can do
2. **Better UX**: Users can set values for empty fields through the agent
3. **Batch Operations**: Can mix UPDATE and CREATE in same request
4. **Clear Semantics**: `metadata_id` = update, `key_id` = create

## Testing

To test the fix:

1. Find a contract with empty metadata fields (`id: null` in GET response)
2. Use the agent to set a value for that field
3. The agent should use `key_id` and succeed
4. Verify the new metadata record is created with a new ID

## API Format Reference

### UPDATE Existing Metadata

```json
{
  "params": {
    "list": [
      {
        "id": 90429,
        "value": "Updated value"
      }
    ]
  }
}
```

### CREATE New Metadata Value

```json
{
  "params": {
    "list": [
      {
        "key_id": 4,
        "value": "New value"
      }
    ]
  }
}
```

### Mixed Batch (UPDATE + CREATE)

```json
{
  "params": {
    "list": [
      {
        "id": 90429,
        "value": "Update existing"
      },
      {
        "key_id": 4,
        "value": "Create new"
      }
    ]
  }
}
```

## Files Changed

1. `app/schemas/metadata_crud.py`
   - Updated `MetadataUpdateItem` to accept `key_id`
   - Added validator for mutual exclusivity
   - Updated `UpdateMetadataAction` validator

2. `app/services/chatbot/tools/metadata_crud/update_metadata.py`
   - Added `key_metadata_map` for lookup by key_id
   - Added CREATE operation support
   - Updated all logging and error messages

3. `app/services/chatbot/tools/metadata_crud/read_metadata.py`
   - Added `key_id` to extracted metadata

4. `app/services/chatbot/tools/metadata_crud/metadata_crud_tools.py`
   - Updated tool descriptions for clarity

5. `app/api/v1/metadata_crud.py`
   - Updated execution endpoint to handle `key_id`

6. `docs/METADATA_UPDATE_GUIDE.md`
   - Added CREATE operation documentation
   - Added mixed batch examples

## Related Issues

This fix resolves the issue where the agent could not set values for metadata fields that exist in the contract template but have no value yet (empty fields with `id: null`).

