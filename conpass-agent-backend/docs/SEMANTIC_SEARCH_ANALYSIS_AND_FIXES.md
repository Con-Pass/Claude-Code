# Semantic Search Tool Analysis and Fixes

## Date: December 15, 2025

## Issues Identified

### 1. **Non-Deterministic Results**

**Problem**: Same query returning different results on repeated calls.

**Root Causes**:

- RRF (Reciprocal Rank Fusion) can produce non-deterministic ordering when scores are tied
- No explicit tie-breaking mechanism in the search results
- Points were returned in potentially varying order from Qdrant

**Solution**:

- Added deterministic sorting by score (descending) then by point ID (ascending)
- Applied to both hybrid search and dense fallback search
- Ensures consistent ordering for identical queries

### 2. **Few Unique Contract IDs Despite 100 Results**

**Problem**: Getting 100 points from Qdrant but only 5-10 unique contract IDs in final results.

**Root Cause**:

- Deduplication logic in `_format_sources()` keeps only the highest-scoring chunk per `contract_id`
- When Qdrant returns 100 chunks from only 10 contracts (10 chunks per contract), deduplication reduces to 10 results
- This was working as designed but not clearly documented

**Solution**:

- Made deduplication behavior configurable via `deduplicate_by_contract` parameter
- Default is `True` (keeps only highest-scoring chunk per contract) - maintains current behavior
- Can be set to `False` to return all chunks if needed
- Added comprehensive logging to track before/after deduplication

### 3. **Insufficient Logging**

**Problem**: Hard to diagnose issues without visibility into search results.

**Solution**:

- Added logging for contract_id distribution in search results
- Added logging for deduplication impact
- Logs now show: total points, unique contracts before/after processing

## Changes Made

### 1. Added Deterministic Sorting

**In `_search_qdrant_hybrid()`** (lines 202-218):

```python
# Sort by score descending, then by ID ascending for deterministic ordering
# This prevents non-deterministic results when RRF fusion produces tied scores
points.sort(key=lambda p: (-p["score"], str(p["id"])))

# Log statistics about contract_id distribution
contract_ids = [
    p.get("payload", {}).get("contract_id")
    for p in points
    if p.get("payload", {}).get("contract_id") is not None
]
unique_contracts = len(set(contract_ids))
logger.info(
    f"Hybrid search returned {len(points)} results from {unique_contracts} unique contracts"
)
```

**In `_search_qdrant_dense_fallback()`** (lines 258-275):

```python
# Sort by score descending, then by ID ascending for deterministic ordering
points.sort(key=lambda p: (-p.get("score", 0.0), str(p.get("id", ""))))

# Log statistics about contract_id distribution
contract_ids = [
    p.get("payload", {}).get("contract_id")
    for p in points
    if p.get("payload", {}).get("contract_id") is not None
]
unique_contracts = len(set(contract_ids))
logger.info(
    f"Dense fallback search returned {len(points)} results from {unique_contracts} unique contracts"
)
```

### 2. Made Deduplication Configurable

**Updated `_format_sources()`** (lines 265-343):

- Added `deduplicate_by_contract: bool = True` parameter
- When `True`: keeps only highest-scoring chunk per contract_id
- When `False`: returns all chunks
- Added logging to show deduplication impact
- Added `score` field to output for debugging

**Updated `semantic_search()`** (lines 370-410):

- Added `deduplicate_by_contract: bool = True` parameter
- Passes parameter through to `_format_sources()`
- Updated docstring to document the parameter

### 3. Enhanced Logging

All search operations now log:

- Total number of points/chunks returned
- Number of unique contracts in the results
- Impact of deduplication (before/after counts)

## Configuration

### Current Settings

From `app/core/config.py`:

- `TOP_K = 100` - Returns up to 100 chunks from Qdrant
- Hybrid search prefetches `top_k * 2` (200) results from each vector type for fusion
- Final RRF fusion returns `top_k` (100) results

### Recommended Adjustments

If you want more unique contracts in results:

**Option 1**: Increase TOP_K

```python
# In .env or config
TOP_K=200  # Get more results from Qdrant, more likely to have more unique contracts
```

**Option 2**: Disable deduplication

```python
# In tools.py where get_semantic_search_tool is called
tools.append(
    get_semantic_search_tool(
        directory_ids=directory_ids,
        deduplicate_by_contract=False  # Return all chunks, not just highest per contract
    )
)
```

**Option 3**: Hybrid approach

- Keep TOP_K high (e.g., 200)
- Keep deduplication enabled
- This ensures you get many results but only the best chunk from each contract

## Why Deduplication Exists

The deduplication logic was added because:

1. **LLM Context Efficiency**: Multiple chunks from same contract provide diminishing returns
2. **Discovery Use Case**: Tool is designed to find "WHICH contracts" mention something, not to extract all content
3. **Cost Optimization**: Fewer tokens sent to LLM = lower costs
4. **Better UX**: More diverse results across contracts vs. many chunks from few contracts

For detailed content extraction from a specific contract, the `read_contracts_tool` should be used instead.

## Testing Recommendations

To verify deterministic behavior:

1. Run the same query 10 times
2. Compare the `contract_id` and `score` values in results
3. Results should be identical across all runs

Example test query:

```python
query = "What are the payment terms?"
results1 = await semantic_search(directory_ids, query)
results2 = await semantic_search(directory_ids, query)
results3 = await semantic_search(directory_ids, query)

# Should be True
assert results1 == results2 == results3
```

## Monitoring

Watch for these log messages to understand behavior:

```
Hybrid search returned 100 results from 45 unique contracts
_format_sources: Processing 100 points
_format_sources: After deduplication, 45 unique contracts (reduced from 100 points)
```

If you consistently see very few unique contracts (e.g., < 10) from 100 results, it may indicate:

- Data quality issue (many duplicate/similar chunks)
- Need to adjust chunk size or overlap in ingestion
- Need to review query relevance

## Backward Compatibility

✅ All changes maintain backward compatibility:

- Default behavior unchanged (deduplication enabled)
- Existing code will work without modifications
- New parameter is optional with sensible default
- Enhanced logging only adds information, doesn't change behavior

## Related Files

- `app/services/chatbot/tools/semantic_search/semantic_search_tool.py` - Main implementation
- `app/services/chatbot/tools/semantic_search/sparse_query.py` - Sparse embedding generation
- `app/services/chatbot/tools/tools.py` - Tool registration
- `app/core/config.py` - Configuration settings
