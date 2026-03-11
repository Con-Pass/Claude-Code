# Source Nodes Streaming Fix

## Problem

Source nodes were not being displayed in the frontend streaming response, even though they were being correctly extracted by the agent (as shown in logs: "Source nodes: 5").

## Root Cause

There was a **race condition** in the streaming response flow:

1. `agent_adapter.py` creates a `StreamingAgentChatResponse` object and immediately returns it
2. A background task in the adapter processes workflow events and populates `source_nodes` when `ToolCallResult` events are received
3. `vercel_response.py` awaits the response and immediately tries to access `result.source_nodes`
4. At this point, the background task hasn't yet received/processed the `ToolCallResult` events, so `source_nodes` is empty

### Code Flow

```
vercel_response.py:118 → await response (returns immediately)
                      ↓
vercel_response.py:130 → Access result.source_nodes (EMPTY!)
                      ↓
agent_adapter.py:128  → Background task processes ToolCallResult
agent_adapter.py:176  → set_source_nodes() is called (TOO LATE!)
```

## Solution

Added a **synchronization mechanism** in `vercel_response.py` that waits for source nodes to be populated before yielding them to the frontend:

```python
# Wait for source nodes to be populated by the background task
max_wait_time = 30  # Maximum 30 seconds to wait for source nodes
wait_interval = 0.1  # Check every 100ms
elapsed_time = 0

while not result.source_nodes and elapsed_time < max_wait_time:
    await asyncio.sleep(wait_interval)
    elapsed_time += wait_interval
    # Check if sources are available and force update if needed
    if hasattr(result, 'sources') and result.sources:
        if hasattr(result, 'set_source_nodes'):
            result.set_source_nodes()
        break
```

## Changes Made

### `app/services/chatbot/vercel_response.py`

1. Added `asyncio` import at the top
2. Added polling loop in `_chat_response_generator()` to wait for source nodes before yielding them
3. Added fallback to manually call `set_source_nodes()` if sources are available but source_nodes aren't populated yet
4. Added debug logging to track how long it takes for source nodes to become available

## Testing

To verify the fix works:

1. Start the server: `uv run uvicorn app.main:app --reload`
2. Send a chat request that triggers the query engine tool
3. Check that the response includes source nodes with metadata
4. Verify in logs: `Source nodes available after X.XXs: N nodes`

## Related Files

- `app/services/chatbot/agent_adapter.py` - Where source_nodes are populated asynchronously
- `app/services/chatbot/vercel_response.py` - Where source_nodes are consumed for frontend
- `app/api/v1/chat.py` - Chat endpoint that uses the streaming response

## Future Improvements

1. Consider using event-based synchronization instead of polling (e.g., asyncio.Event)
2. Add metrics to track source node availability timing
3. Consider making the wait timeout configurable
4. Add warning if timeout is reached without source nodes
