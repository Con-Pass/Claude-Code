# Filter Generation and Validation Improvements

## Problem Summary

The filter generation system was failing consistently with the query "get me contracts from 5970 to 5990". The LLM (Gemini 2.5 Flash) was generating filters with both `match` and `range` keys in a single FieldCondition, even though the validation clearly stated this was incorrect. The specific error pattern was:

```json
{
  "key": "contract_id",
  "match": {
    "any": [5970, 5971, ..., 5990]
  },
  "range": null  // ❌ THIS IS THE PROBLEM
}
```

Even after 3 retry attempts with explicit feedback, the LLM kept making the same mistake.

## Root Causes

### 1. **Pydantic Serialization Issue**
When using `model_dump()` or `model_dump_json()` on Pydantic models, fields with `None` values were being included in the output. This meant that even though the LLM was trying to use only `match`, the `range` field was appearing as `"range": null` in the JSON.

### 2. **LLM Not Learning from Feedback**
The validation feedback was correct but not specific enough about the exact fix needed. The LLM kept regenerating the same pattern even with feedback.

### 3. **Insufficient Prompt Emphasis**
While the prompt warned about not using both `match` and `range`, it didn't strongly emphasize that having `"range": null` or `"match": null` in the output was equally problematic.

## Solutions Implemented

### 1. **Pydantic Model Enhancements** ✅

Added `exclude_none=True` by default to all critical model classes to prevent `None` values from appearing in serialized output:

**File: `app/services/chatbot/tools/metadata_search/qdrant_filter.py`**

```python
class FieldCondition(QdrantBaseModel):
    # ... fields ...
    
    def model_dump(self, **kwargs):
        """Override to exclude None values by default"""
        kwargs.setdefault('exclude_none', True)
        return super().model_dump(**kwargs)
    
    def model_dump_json(self, **kwargs):
        """Override to exclude None values by default"""
        kwargs.setdefault('exclude_none', True)
        return super().model_dump_json(**kwargs)
```

Applied to:
- `FieldCondition`
- `RangeCondition`
- `Filter`
- `NestedFilter`

### 2. **Enhanced Prompt with Stronger Warnings** ✅

**File: `app/services/chatbot/tools/metadata_search/prompts.py`**

Added multiple layers of emphasis:

1. **In the Condition Types section:**
```markdown
**⚠️ CRITICAL: FieldCondition Rules:**
- Each FieldCondition must have ONLY ONE of: `match` OR `range`
- **DO NOT include both `match` and `range` keys in the same FieldCondition object, even if one is null**
- **DO NOT include unused keys at all - completely omit them from your JSON output**
- ✅ CORRECT: `{"key": "field", "match": {"value": "ABC"}}`  ← No "range" key at all
- ❌ WRONG: `{"key": "field", "match": {"value": "ABC"}, "range": null}` ← "range": null is FORBIDDEN
```

2. **In the Structure Requirements section:**
Added explicit examples of what's wrong including null values in ranges:
```markdown
- ❌ WRONG: `{"range": {"gte": "2024-01-01", "lte": "2024-12-31", "gt": null, "lt": null}}`
- ✅ CORRECT: `{"range": {"gte": "2024-01-01", "lte": "2024-12-31"}}`
```

3. **Enhanced Final Pre-Output Check:**
Added comprehensive checklist items:
```markdown
5. **⚠️ CRITICAL - Does my JSON contain ANY null values?**
   - If YES → ❌ THIS IS WRONG! Remove those keys entirely from your JSON
   - Common mistakes: `"range": null`, `"match": null`, `"gt": null`, `"lt": null`

6. **⚠️ FINAL SCAN - Look at EVERY FieldCondition in your output:**
   - Count the number of top-level keys (should be exactly 2: "key" and either "match" OR "range")
   - If you see 3 keys ("key", "match", "range") → ❌ WRONG! Remove one
```

### 3. **Improved Validation Error Messages** ✅

**File: `app/services/chatbot/tools/metadata_search/text_to_qdrant_filters.py`**

Enhanced `_validate_filter_structure()` to:

1. Check for the presence of both keys (not just non-null values)
2. Provide more specific error messages with clear solutions

```python
def validate_range_condition(condition: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    has_match = "match" in condition
    has_range = "range" in condition
    
    if has_match and has_range:
        return (
            False,
            f"FieldCondition cannot have both 'match' and 'range' keys on field '{condition.get('key', 'unknown')}'. "
            f"A FieldCondition should contain ONLY 'match' OR ONLY 'range', not both. "
            f"Even if one is null (like 'range': null), having both keys is incorrect. "
            f"SOLUTION: Remove the unused key entirely from the JSON. "
            f"If you need to filter by both contract_id and date, create TWO separate FieldCondition objects in the 'must' array.",
        )
```

Enhanced validation prompt feedback:
```markdown
2. **FieldCondition with Both Match AND Range (MOST COMMON ERROR #2)**:
   - ❌ **REJECT IMMEDIATELY**: If ANY FieldCondition has BOTH `match` AND `range` keys (even if one is null)
   - ❌ **REJECT IMMEDIATELY**: If you see `"range": null` or `"match": null` anywhere in the filter
   - **To fix**: Tell the LLM to "Remove the 'range' key entirely from the FieldCondition"
```

### 4. **Post-Generation Cleanup Safety Net** ✅

**File: `app/services/chatbot/tools/metadata_search/text_to_qdrant_filters.py`**

Added a cleanup function that recursively removes all `None` values as a last resort:

```python
def _clean_filter_dict(filter_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively clean a filter dictionary by removing all None values.
    This is a safety net in case the LLM generates filters with null values.
    """
    if not isinstance(filter_dict, dict):
        return filter_dict
    
    cleaned = {}
    for key, value in filter_dict.items():
        if value is None:
            # Skip None values entirely
            continue
        elif isinstance(value, dict):
            # Recursively clean nested dicts
            cleaned_value = _clean_filter_dict(value)
            if cleaned_value:
                cleaned[key] = cleaned_value
        elif isinstance(value, list):
            # Clean each item in the list
            cleaned_list = []
            for item in value:
                if isinstance(item, dict):
                    cleaned_item = _clean_filter_dict(item)
                    if cleaned_item:
                        cleaned_list.append(cleaned_item)
                elif item is not None:
                    cleaned_list.append(item)
            if cleaned_list:
                cleaned[key] = cleaned_list
        else:
            cleaned[key] = value
    
    return cleaned
```

Applied after LLM generation:
```python
# Safety net: Clean the filter response to remove any None values
if filter_response.filter:
    filter_dict = filter_response.filter.model_dump(exclude_none=True)
    cleaned_filter_dict = _clean_filter_dict(filter_dict)
    filter_response.filter = Filter(**cleaned_filter_dict)
```

### 5. **Consistent Use of exclude_none** ✅

Updated all serialization calls to use `exclude_none=True`:

```python
# In _generate_filter():
filter_json = filter_response.model_dump_json(indent=2, exclude_none=True)

# In _validate_filter():
filter_json = filter_response.model_dump_json(indent=2, exclude_none=True)

# When validating structure:
filter_dict = filter_response.filter.model_dump(exclude_none=True)
```

## Expected Improvements

### 1. **Reduced Validation Failures**
- Pydantic models now automatically exclude `None` values
- Even if LLM tries to include them, they'll be stripped out

### 2. **Better LLM Understanding**
- Multiple layers of emphasis in prompt
- Clear examples of what's wrong and what's right
- Explicit checklist before output

### 3. **Stronger Safety Nets**
- Post-generation cleanup catches any `None` values that slip through
- More specific validation error messages guide the LLM better
- Enhanced structural validation catches the error earlier

### 4. **Clearer Error Messages**
- Validation now explicitly says to "Remove the 'range' key entirely"
- Provides context about why it's wrong
- Suggests concrete solutions

## Testing Recommendations

Test with the problematic query:
```
"get me contracts from 5970 to 5990"
```

Expected successful output:
```json
{
  "filter": {
    "must": [
      {
        "key": "contract_id",
        "match": {
          "any": [5970, 5971, 5972, ..., 5990]
        }
      }
    ]
  }
}
```

The output should NOT contain:
- `"range": null` anywhere
- `"match": null` anywhere  
- Any other fields with `null` values (except top-level "filter" when appropriate)

## Additional Test Cases

1. **Contract ID range + date range** (ensure two separate FieldConditions):
```
"From contract range 5900 to 5995, identify which expire this year"
```

Expected: Two separate FieldConditions in `must` array

2. **Simple date range**:
```
"Contracts ending in December 2025"
```

Expected: Single FieldCondition with only `range`, no `match` key

3. **Simple ID match**:
```
"Show me contract 5851"
```

Expected: Single FieldCondition with only `match`, no `range` key

## Summary of Changes

| Component | Change | Impact |
|-----------|--------|--------|
| Pydantic Models | Added `exclude_none=True` to model_dump methods | Prevents `None` values in serialization |
| Prompt Template | Enhanced warnings and examples | Better LLM understanding |
| Validation Logic | Check for key presence, not just values | Catches errors earlier |
| Validation Feedback | More specific error messages | Better guidance for retries |
| Post-Generation | Added cleanup safety net | Last-resort protection |
| All Serialization | Consistent use of `exclude_none=True` | Unified behavior |

## Files Modified

1. `app/services/chatbot/tools/metadata_search/qdrant_filter.py`
   - Added `model_dump()` and `model_dump_json()` overrides to 4 classes

2. `app/services/chatbot/tools/metadata_search/prompts.py`
   - Enhanced warnings in multiple sections
   - Added more explicit examples
   - Expanded pre-output checklist

3. `app/services/chatbot/tools/metadata_search/text_to_qdrant_filters.py`
   - Added `_clean_filter_dict()` function
   - Enhanced `_validate_filter_structure()` logic
   - Updated all serialization to use `exclude_none=True`
   - Added post-generation cleanup step

## Architecture Decision

The solution uses a **defense-in-depth** approach:

1. **Prevention** (Pydantic model overrides)
2. **Prompt Engineering** (Enhanced instructions)
3. **Validation** (Improved error detection)
4. **Recovery** (Cleanup safety net)

This ensures that even if one layer fails, others catch the issue.
