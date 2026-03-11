# Query Engine Tool Fix

## Problem Identified

Your query_engine tool wasn't working properly because it was still using the **old `AgentRunner` pattern with `CallbackManager`**, which is incompatible with the new `AgentWorkflow` system.

### Issues Found:

1. **❌ CallbackManager dependency**: The code was creating and using `CallbackManager` which AgentWorkflow doesn't support the same way
2. **❌ IndexConfig with callback_manager**: Index was being created with callback_manager requirement
3. **❌ No error handling**: If index loading failed, it would crash the entire chat engine
4. **❌ No logging**: Difficult to debug when the tool wasn't working

## Changes Made

### 1. Fixed `app/services/chatbot/engine.py`

**Before:**

```python
from llama_index.core.callbacks import CallbackManager

def get_chat_engine(...):
    callback_manager = CallbackManager(handlers=event_handlers or [])

    # Add query tool if index exists
    index_config = IndexConfig(callback_manager=callback_manager, **(params or {}))
    index = get_index(index_config)
    if index is not None:
        query_engine_tool = get_query_engine_tool(index, **kwargs)
        tools.append(query_engine_tool)
```

**After:**

```python
from app.core.logging_config import get_logger

logger = get_logger(__name__)

def get_chat_engine(...):
    # Note: AgentWorkflow doesn't use CallbackManager the same way
    # Event handlers are passed to the adapter instead

    # Add query tool if index exists
    try:
        logger.info("Loading index for query engine tool...")
        index = get_index()  # No callback_manager needed
        if index is not None:
            query_engine_tool = get_query_engine_tool(index, **kwargs)
            tools.append(query_engine_tool)
            logger.info("Query engine tool added successfully")
        else:
            logger.warning("Index is None, skipping query engine tool")
    except Exception as e:
        logger.warning(f"Could not load index for query engine tool: {e}")
```

**Key improvements:**

- ✅ Removed `CallbackManager` dependency
- ✅ Added try-catch for error handling
- ✅ Added logging for debugging
- ✅ Graceful failure - if index fails to load, contract tools still work

### 2. Updated `app/services/chatbot/index.py`

**Before:**

```python
def get_index(config: IndexConfig = None):
    if config is None:
        config = IndexConfig()
    # ...
    index = VectorStoreIndex.from_vector_store(
        store, callback_manager=config.callback_manager
    )
    return index
```

**After:**

```python
def get_index(config: IndexConfig = None):
    if config is None:
        config = IndexConfig()
    # ...

    # Only pass callback_manager if it's provided (for backward compatibility)
    kwargs = {}
    if config.callback_manager is not None:
        kwargs["callback_manager"] = config.callback_manager

    index = VectorStoreIndex.from_vector_store(store, **kwargs)
    return index
```

**Key improvements:**

- ✅ Made `callback_manager` truly optional
- ✅ Backward compatible with old code that passes callback_manager
- ✅ Works with new AgentWorkflow that doesn't provide it

## How AgentWorkflow Handles Query Engine Events

### Old AgentRunner Pattern:

```
AgentRunner → CallbackManager → Index with callbacks
                    ↓
          Event handlers receive events
```

### New AgentWorkflow Pattern:

```
AgentWorkflow → Index (no callbacks needed)
      ↓
  Tool execution
      ↓
  ToolCall/ToolCallResult events
      ↓
  WorkflowAgentChatAdapter transforms to callback events
      ↓
  Event handlers receive events
```

**Key difference**: The query engine tool is just a regular tool now. Events are captured at the workflow level, not at the index level.

## Testing Your Query Engine Tool

### 1. Check if tool is loaded:

Look for this in your logs when starting the server:

```
INFO: Loading index for query engine tool...
INFO: Connecting vector store...
INFO: Finished load index from vector store.
INFO: Query engine tool added successfully
```

### 2. Test with a query:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Search the documents for information about X"}],
    "data": {"type": "general", "user": {...}}
  }'
```

### 3. Check tool is being called:

Look for these events in the streaming response:

- `FUNCTION_CALL` event with tool name `semantic_search`
- `AGENT_STEP` event with the query results

## Tool Configuration

Your query engine tool is configured in `app/services/chatbot/tools/query_engine.py`:

```python
def get_query_engine_tool(index, name=None, description=None, **kwargs):
    if name is None:
        name = "semantic_search"
    if description is None:
        description = (
            "Use this tool to retrieve information about the text corpus from an index."
        )
    # ...
```

**The agent will use this tool when:**

- User asks about information in uploaded documents
- User queries the knowledge base
- User asks "what's in the documents?"

## Troubleshooting

### Issue: Tool not being called

**Solution**: Check the tool description. Make sure it clearly describes when to use it.

**Current description**:

```
"Use this tool to retrieve information about the text corpus from an index."
```

**Better description** (if needed):

```python
description = (
    "Use this tool to search through uploaded documents and retrieve relevant information. "
    "Call this when the user asks about content in documents, wants to search the knowledge base, "
    "or needs information from previously uploaded files."
)
```

### Issue: Index not loading

**Check:**

1. Vector store is accessible:
   ```python
   # In index.py
   store = get_vector_store()
   ```
2. Check logs for error messages
3. Verify `storage/` directory exists and has index files

### Issue: Tool returns empty results

**Check:**

1. `TOP_K` setting in config: `settings.TOP_K`
2. Similarity threshold
3. Whether documents are actually indexed

### Issue: Events not showing up

**This is now working correctly** because:

- ToolCall events → Transformed to FUNCTION_CALL callbacks
- ToolCallResult events → Transformed to AGENT_STEP callbacks
- WorkflowAgentChatAdapter handles the transformation

## Summary

### ✅ What's Fixed:

- Query engine tool now works with AgentWorkflow
- No more CallbackManager dependency issues
- Proper error handling and logging
- Graceful failure if index can't load

### ✅ What's Preserved:

- Same tool interface
- Same query engine functionality
- Same event emission (via adapter transformation)
- Backward compatible if callback_manager is provided

### ✅ What's Improved:

- Better error messages
- Detailed logging for debugging
- Won't crash if index fails to load
- Clearer code structure

Your query engine tool should now work perfectly with the new AgentWorkflow system! 🎉

## Next Steps

1. **Restart your server** to apply the changes
2. **Check logs** for "Query engine tool added successfully"
3. **Test with a query** that should use the index
4. **Monitor events** in the streaming response

If you still have issues, check:

- Is the vector store accessible?
- Are documents indexed in `storage/`?
- Does the tool description make it clear when to use it?
- Are logs showing any errors?
