# Chat History Implementation Summary

## Quick Overview

This document provides a concise summary of the chat history feature implementation plan.

**Storage**: Uses abstraction layer supporting both Redis (interim) and Firestore (production). See `CHAT_HISTORY_INTERIM_STORAGE.md` for Redis details.

## Key Components

### 1. **User Identification**

- Extract `user_id` from JWT token via ConPass API `/user` endpoint
- Cache user_id to reduce API calls
- Service: `app/services/user_service.py`

### 2. **Storage Structure**

**Interim Solution (Redis)**:

- Key: `chat_sessions_chatdata:{user_id}:{chat_id}` (Hash - ChatData format)
- Key: `chat_sessions_payload:{user_id}:{chat_id}` (Hash - Client payload format)
- Key: `chat_list:{user_id}` (Sorted Set - for pagination)

**Production Solution (Firestore)** - When available:

- Collection: `chat_sessions_chatdata` - ChatData format
- Collection: `chat_sessions_payload` - Client payload format

Both use abstraction layer for easy migration.

### 3. **API Endpoints**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/chat` | POST | Create/continue chat (modified) |
| `/v1/chat/history` | GET | List user's chats |
| `/v1/chat/{chat_id}` | GET | Get full chat with messages |
| `/v1/chat/{chat_id}` | DELETE | Delete chat |

### 4. **Modified Files**

**Existing Files to Modify:**

- `app/api/v1/chat.py` - Add chat_id support and message saving
- `app/services/chatbot/vercel_response.py` - Track messages for saving
- `app/schemas/chat.py` - Add chat_id to SessionData
- `app/core/config.py` - Add Firestore configuration (when available)

**New Files to Create:**

- `app/services/user_service.py` - User ID extraction
- `app/services/chat_history/storage_interface.py` - Abstract storage interface
- `app/services/chat_history/redis_storage.py` - Redis implementation (interim)
- `app/services/chat_history/firestore_storage.py` - Firestore implementation (when ready)
- `app/services/chat_history/storage_factory.py` - Factory to select implementation
- `app/schemas/chat_history.py` - Chat history schemas
- `app/api/v1/chat_history.py` - History endpoints

## Critical Edge Cases

1. **User ID extraction fails** → Return 503, don't proceed
2. **Chat not found** → Return 404
3. **Chat belongs to different user** → Return 403
4. **Firestore write fails** → Log error, chat still works (degraded mode)
5. **Streaming interrupted** → Save messages sent before disconnection
6. **Concurrent updates** → Use Firestore transactions
7. **Large message history** → Paginate message retrieval
8. **Invalid message format** → Validate and skip invalid messages

## Security Checklist

- ✅ User isolation (users can only access their chats)
- ✅ Input validation (Pydantic schemas)
- ✅ JWT token validation (existing middleware)
- ✅ Rate limiting (prevent abuse)
- ✅ Data privacy (GDPR-compliant deletion)

## Performance Optimizations

1. **Caching**: User ID, chat lists, chat details
2. **Pagination**: Limit results (default 20, max 100)
3. **Batch Writes**: Group message writes (Redis pipeline or Firestore batch limit: 500)
4. **Lazy Loading**: Load messages only when needed
5. **Indexes**: Redis uses sorted sets (no indexes needed), Firestore requires composite indexes

## Storage Indexes Required

**Interim (Redis)**: No indexes needed! Uses sorted sets for pagination.

**Production (Firestore)** - When available:
**For both collections** (`chat_sessions_chatdata` and `chat_sessions_payload`):

```text
1. user_id (ASC) + updated_at (DESC)
2. user_id (ASC) + session_type (ASC) + updated_at (DESC)
```

## Implementation Phases

### Phase 1: Foundation

- Firestore setup
- User service
- Firestore service layer
- Schemas

### Phase 2: Core Functionality

- API endpoints
- Chat endpoint modification
- Message saving integration

### Phase 3: Edge Cases & Polish

- Error handling
- Caching
- Monitoring
- Performance optimization

### Phase 4: Testing & Deployment

- E2E testing with both collections
- Load testing both formats
- Security audit
- Gradual rollout
- Monitor both collections

### Phase 5: Format Selection & Cleanup

- Analyze performance of both formats
- Decide which format works better
- Update code to use only chosen collection
- Delete unused collection

## Dependencies

**Interim (Redis)**: No new dependencies! Uses existing Redis setup.

**Production (Firestore)** - When available:

```toml
google-cloud-firestore>=2.14.0
```

## Configuration

**Interim (Redis)**: Uses existing `REDIS_URL` - no additional config needed!

**Production (Firestore)** - When available:

```python
# app/core/config.py
FIRESTORE_PROJECT_ID: str
FIRESTORE_CREDENTIALS_PATH: Optional[str] = None
FIRESTORE_DATABASE_ID: Optional[str] = None
USE_FIRESTORE: bool = False  # Set to True when switching
```

## Backward Compatibility

- `chat_id` is optional in existing endpoint
- Existing clients work without changes
- No breaking changes to response format

## Testing Requirements

- Unit tests for all services
- Integration tests for API endpoints
- Load tests for concurrent access
- Security tests for user isolation

## Monitoring Metrics

- Chat creation rate
- Retrieval latency
- Firestore write success rate
- Cache hit rate
- Error rates by type

## Next Steps

1. Review and approve architecture
2. Set up Firestore project
3. Implement Phase 1 components
4. Test with sample data
5. Iterate through remaining phases

---

For detailed architecture, see `CHAT_HISTORY_ARCHITECTURE.md`
