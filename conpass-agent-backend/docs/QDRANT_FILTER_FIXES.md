# Qdrant Filter Tool - Issue Fixes

## Issues Encountered & Solutions

### Issue 1: OpenAI Structured Output Error

**Error Message**:

```
Error code: 400 - {'error': {'message': "Invalid schema for response_format 'QdrantFilterResponse':
In context=(), 'additionalProperties' is required to be supplied and to be false.",
'type': 'invalid_request_error', 'param': 'response_format', 'code': None}}
```

**Root Cause**:
OpenAI's structured output API requires all Pydantic models to have `additionalProperties: false` in their JSON schema. This is enforced by setting `extra = "forbid"` in the Pydantic model's Config.

**Fix Applied**:

```python
# Before (WRONG)
class Filter(BaseModel):
    must: Optional[List[...]] = Field(...)
    should: Optional[List[...]] = Field(...)
    must_not: Optional[List[...]] = Field(...)

    class Config:
        extra = "allow"  # ❌ This causes the error

# After (CORRECT)
class Filter(BaseModel):
    must: Optional[List[...]] = Field(...)
    should: Optional[List[...]] = Field(...)
    must_not: Optional[List[...]] = Field(...)

    class Config:
        extra = "forbid"  # ✅ Required for OpenAI structured output
```

**Files Changed**:

- `app/schemas/qdrant_filter.py` - Added `extra = "forbid"` to both `Filter` and `QdrantFilterResponse` classes

---

### Issue 2: Unnecessary Complexity with qdrant-client

**Problem**:
Using the `qdrant-client` library required:

1. Converting dict filters to Qdrant model objects
2. Extra dependency on `qdrant-client`
3. More complex code with model conversions

**Solution**:
Replaced with direct HTTP API calls using `httpx`:

```python
# Before (Complex)
from qdrant_client import QdrantClient
from qdrant_client.http import models

client = get_qdrant_client()
filter_model = models.Filter(**qdrant_filter)  # Conversion needed
scroll_result = await loop.run_in_executor(
    None,
    lambda: client.scroll(
        collection_name=collection_name,
        scroll_filter=filter_model,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    ),
)

# After (Simple)
import httpx

endpoint = f"{url}/collections/{collection_name}/points/scroll"
body = {
    "limit": limit,
    "with_payload": True,
    "with_vector": False,
    "filter": qdrant_filter  # Direct dict, no conversion!
}

async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.post(endpoint, json=body, headers=headers)
    response.raise_for_status()

data = response.json()
points = data.get("result", {}).get("points", [])
```

**Benefits**:

- ✅ No model conversion needed
- ✅ Simpler, more readable code
- ✅ Direct control over HTTP requests
- ✅ `httpx` already included in `fastapi[standard]`
- ✅ Fewer dependencies

**Files Changed**:

- `app/services/chatbot/qdrant_client.py` - Completely rewrote to use HTTP API

---

## Testing the Fix

Run the test to verify everything works:

```bash
python examples/qdrant_filter_usage.py
```

Expected output:

```
=== Simple Metadata Queries ===

1. Find contracts with a specific company:
Query: Show me contracts with 株式会社ABC
Filter reasoning: Filtering for contracts where company_a matches 株式会社ABC
Found X result(s)
...
```

## Summary

Both issues are now fixed:

1. ✅ OpenAI structured output error resolved by using `extra = "forbid"`
2. ✅ Simplified implementation by using direct HTTP API calls

The tool now:

- Works correctly with OpenAI's structured output
- Uses simpler, more maintainable HTTP calls
- Requires no conversion between dict and Qdrant models
- Has fewer dependencies (no special qdrant-client usage)
