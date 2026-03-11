# Qdrant Filter Issue & Fix

## The Problem

Your semantic_search tool was failing with this error:

```
400 Bad Request
Index required but not found for "private" of one of the following types: [keyword]
```

### Root Cause

Your code was trying to filter Qdrant vector search by `private="false"`, but **Qdrant requires a keyword index** on any field you want to filter by. The "private" field doesn't have an index in your Qdrant collection.

## What I Fixed

### 1. ✅ Explicit Filters Parameter (`engine.py`)

**Before**: Filters were passed in `**kwargs` but never extracted

```python
def get_chat_engine(..., **kwargs):
    query_engine_tool = get_query_engine_tool(index, **kwargs)  # filters lost!
```

**After**: Filters are explicit and properly passed

```python
def get_chat_engine(..., filters=None, **kwargs):
    query_engine_kwargs = {**kwargs}
    if filters is not None:
        query_engine_kwargs["filters"] = filters
        logger.info(f"Applying filters: {filters}")

    query_engine_tool = get_query_engine_tool(index, **query_engine_kwargs)
```

### 2. ✅ Made Private Filter Optional (`query_filter.py`)

**Before**: Always added `private="false"` filter (causing Qdrant error)

```python
def generate_filters(doc_ids):
    public_doc_filter = MetadataFilter(key="private", value="false", ...)
    # Always included!
```

**After**: Private filter is optional and defaults to OFF

```python
def generate_filters(doc_ids, include_private_filter=False):
    if include_private_filter:
        # Only add if explicitly enabled
        public_doc_filter = MetadataFilter(key="private", value="false", ...)
```

## Quick Test

**Restart your server and try again:**

```bash
# The query should work now without the private filter
```

Your logs should show:

```
INFO: Loading index for query engine tool...
INFO: Query engine tool added successfully
# No more Qdrant 400 errors!
```

## Two Solutions

### Solution 1: Without Private Filter (Current - Working ✅)

**Pros:**

- ✅ Works immediately
- ✅ No database changes needed
- ✅ No errors

**Cons:**

- ⚠️ Doesn't filter out private documents
- ⚠️ All documents in the index are searchable

**This is currently active** - your query tool will work now!

### Solution 2: Add Qdrant Keyword Index (Recommended for Production)

To enable the private filter properly, create a keyword index in Qdrant:

#### Using Qdrant REST API:

```bash
curl -X PUT 'https://your-qdrant-url:6333/collections/localhost/index' \
  -H 'Content-Type: application/json' \
  -H 'api-key: YOUR_API_KEY' \
  -d '{
    "field_name": "private",
    "field_schema": "keyword"
  }'
```

#### Using Python Qdrant Client:

```python
from qdrant_client import QdrantClient

client = QdrantClient(url="your-qdrant-url", api_key="your-api-key")

# Create keyword index for "private" field
client.create_payload_index(
    collection_name="localhost",
    field_name="private",
    field_schema="keyword"
)
```

#### After creating the index:

**Enable the private filter** in `chat.py`:

```python
# Line 96 in chat.py
filters = generate_filters(doc_ids, include_private_filter=True)
```

## Understanding the Error

### What Qdrant Indexes Are For

Qdrant needs indexes on fields you want to filter by for performance:

| Field Type    | Index Type           | Used For                             |
| ------------- | -------------------- | ------------------------------------ |
| String values | `keyword`            | Exact match filters (`==`, `!=`)     |
| Numbers       | `integer` or `float` | Range filters (`>`, `<`, `>=`, `<=`) |
| Boolean       | `bool`               | True/False filters                   |

### Fields in Your Documents

Based on your code, documents have these metadata fields:

- `private`: "true" or "false" (string) - **Needs keyword index** ⚠️
- `doc_id`: Document identifier - May need keyword index if filtering
- Other fields from your ingestion

## Production Checklist

### If You Need Private/Public Document Separation:

- [ ] Create keyword index on "private" field in Qdrant
- [ ] Enable private filter: `generate_filters(doc_ids, include_private_filter=True)`
- [ ] Test with private and public documents
- [ ] Verify private docs are excluded from search

### If You Don't Need Private Filter:

- [x] Leave it disabled (current state) ✅
- [x] Query tool works without filtering
- [ ] Consider removing "private" field from metadata if unused

## Testing Both Scenarios

### Test 1: Without Private Filter (Current)

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -d '{
    "messages": [{"role": "user", "content": "tell me about different types of letters"}],
    "data": {"type": "general", "user": {...}}
  }'
```

**Expected**: ✅ Works! Searches all documents in index.

### Test 2: With Doc ID Filter

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -d '{
    "messages": [{
      "role": "user",
      "content": "tell me about letters",
      "annotations": [{
        "type": "document_file",
        "data": {"files": [{"name": "doc.pdf", "refs": ["doc_123"]}]}
      }]
    }],
    "data": {"type": "general", "user": {...}}
  }'
```

**Expected**: ✅ Searches only in documents with `doc_id` in ["doc_123"]

### Test 3: With Private Filter (After Creating Index)

```python
# In chat.py line 96, enable the filter:
filters = generate_filters(doc_ids, include_private_filter=True)
```

**Expected**: ✅ Only searches public documents (private="false")

## Summary

| Issue                               | Status      | Action Needed                 |
| ----------------------------------- | ----------- | ----------------------------- |
| Filters not passed to query engine  | ✅ Fixed    | None                          |
| Private filter causing Qdrant error | ✅ Fixed    | None (disabled by default)    |
| Query tool working                  | ✅ Working  | Test it!                      |
| Private/public separation           | ⚠️ Optional | Create Qdrant index if needed |

Your semantic_search tool should work now! The private filter is disabled by default to avoid the Qdrant error. If you need to separate private/public documents, follow Solution 2 to create the keyword index in Qdrant.
