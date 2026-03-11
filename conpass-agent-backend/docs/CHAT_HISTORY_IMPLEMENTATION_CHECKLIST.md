# Chat History Implementation Checklist

Use this checklist to track progress during implementation.

## Prerequisites

**Interim Solution (Redis)**:

- [ ] Redis is already configured (uses existing `REDIS_URL`)
- [ ] Verify Redis connection is working
- [ ] No additional setup required!

**Production Solution (Firestore)** - When available:

- [ ] Firestore project created and configured
- [ ] Firestore credentials set up (service account or default credentials)
- [ ] Environment variables configured
- [ ] Firestore indexes created (see architecture doc)

## Phase 1: Foundation

### Configuration

**Interim (Redis)**: No configuration needed! Uses existing `REDIS_URL`.

**Production (Firestore)** - When available:

- [ ] Add Firestore config to `app/core/config.py`
  - [ ] `FIRESTORE_PROJECT_ID`
  - [ ] `FIRESTORE_CREDENTIALS_PATH` (optional)
  - [ ] `FIRESTORE_DATABASE_ID` (optional)
  - [ ] `USE_FIRESTORE: bool = False` (set to True when switching)

### Dependencies

**Interim (Redis)**: No new dependencies! Redis is already installed.

**Production (Firestore)** - When available:

- [ ] Add `google-cloud-firestore>=2.14.0` to `pyproject.toml`
- [ ] Install dependencies

### User Service

- [ ] Create `app/services/user_service.py`
- [ ] Implement `get_user_id_from_token()` method
- [ ] Add error handling for ConPass API failures
- [ ] Add caching for user_id (optional)
- [ ] Write unit tests

### Schemas

- [ ] Create `app/schemas/chat_history.py`
- [ ] Define `ChatMessageHistory` model
- [ ] Define `ChatSession` model
- [ ] Define `ChatSessionDetail` model
- [ ] Define `ChatHistoryList` model
- [ ] Define `CreateChatRequest` model (if needed)
- [ ] Define `ContinueChatRequest` model (if needed)
- [ ] Update `app/schemas/chat.py`:
  - [ ] Add `chat_id: Optional[str]` to `SessionData`

### Storage Service (Abstraction Layer)

- [ ] Create `app/services/chat_history/__init__.py`
- [ ] Create `app/services/chat_history/storage_interface.py` (abstract interface)
- [ ] Create `app/services/chat_history/redis_storage.py` (Redis implementation - interim)
- [ ] Create `app/services/chat_history/storage_factory.py` (factory to select implementation)
- [ ] Implement `create_chat()` method in Redis storage
- [ ] Implement `get_chat()` method in Redis storage
- [ ] Implement `list_chats()` method in Redis storage
- [ ] Implement `add_messages()` method in Redis storage
- [ ] Implement `delete_chat()` method in Redis storage
- [ ] Add error handling for all methods
- [ ] Write unit tests for Redis implementation
- [ ] **When Firestore available**: Create `firestore_storage.py` implementing same interface
- [ ] **When Firestore available**: Add transaction support for concurrent writes

## Phase 2: Core Functionality

### Chat History API Endpoints

- [ ] Create `app/api/v1/chat_history.py`
- [ ] Implement `GET /v1/chat/history` endpoint
  - [ ] Extract user_id from JWT
  - [ ] Implement pagination
  - [ ] Implement session_type filtering
  - [ ] Add error handling
  - [ ] Write tests
- [ ] Implement `GET /v1/chat/{chat_id}` endpoint
  - [ ] Extract user_id from JWT
  - [ ] Verify chat ownership
  - [ ] Load chat with messages
  - [ ] Add error handling (404, 403)
  - [ ] Write tests
- [ ] Implement `DELETE /v1/chat/{chat_id}` endpoint
  - [ ] Extract user_id from JWT
  - [ ] Verify chat ownership
  - [ ] Delete chat and messages
  - [ ] Add error handling (404, 403)
  - [ ] Write tests
- [ ] Register router in `app/api/router.py`

### Modify Chat Endpoint

- [ ] Update `app/api/v1/chat.py`:
  - [ ] Extract user_id from JWT token
  - [ ] Check for `chat_id` in request data
  - [ ] Load existing chat if `chat_id` provided
  - [ ] Merge existing messages with new messages
  - [ ] Create new chat if no `chat_id` provided
  - [ ] Pass chat_id to response handler
- [ ] Update `app/services/chatbot/vercel_response.py`:
  - [ ] Track all messages during streaming
  - [ ] Add callback to save messages after streaming
  - [ ] Handle streaming interruption
- [ ] Create background task for saving messages:
  - [ ] Create `app/services/chat_history/message_saver.py`
  - [ ] Implement `save_chat_messages()` function
  - [ ] Add retry logic
  - [ ] Add error logging
- [ ] Write integration tests

## Phase 3: Edge Cases & Polish

### Error Handling

- [ ] Handle user_id extraction failures (503)
- [ ] Handle chat not found (404)
- [ ] Handle unauthorized access (403)
- [ ] Handle storage write failures (log, don't fail chat) - works for both Redis and Firestore
- [ ] Handle streaming interruption
- [ ] Handle concurrent updates (transactions)
- [ ] Handle invalid message format
- [ ] Handle large message history (pagination)

### Title Generation

- [ ] Implement auto-title generation from first message
- [ ] Add fallback for empty messages
- [ ] Truncate long titles
- [ ] Sanitize user-provided titles

### Validation

- [ ] Validate chat_id format
- [ ] Validate message content size limits
- [ ] Validate pagination parameters
- [ ] Add input sanitization

### Caching (Optional but Recommended)

- [ ] Implement user_id caching
- [ ] Implement chat list caching
- [ ] Implement chat detail caching
- [ ] Add cache invalidation on updates
- [ ] Configure cache TTLs

### Performance

- [ ] Optimize storage queries (Redis sorted sets or Firestore queries)
- [ ] Implement batch writes for messages
- [ ] Add pagination limits
- [ ] Optimize message loading (lazy load)
- [ ] For Redis: Optimize hash operations and sorted set pagination

## Phase 4: Testing & Deployment

### Unit Tests

- [ ] Test user service
- [ ] Test Redis storage service (all methods)
- [ ] Test schema validation
- [ ] Test error handling
- [ ] **When Firestore available**: Test Firestore storage service (all methods)

### Integration Tests

- [ ] Test chat history endpoints
- [ ] Test chat endpoint with chat_id
- [ ] Test message saving
- [ ] Test concurrent access
- [ ] Test error recovery

### Load Tests

- [ ] Test concurrent chat creation
- [ ] Test large message history retrieval
- [ ] Test storage write performance (Redis or Firestore)
- [ ] Test cache effectiveness

### Security Tests

- [ ] Test user isolation
- [ ] Test unauthorized access attempts
- [ ] Test input validation
- [ ] Test rate limiting

### Documentation

- [ ] Update API documentation
- [ ] Add endpoint examples
- [ ] Document error codes
- [ ] Update README if needed

### Monitoring

- [ ] Add metrics for chat creation
- [ ] Add metrics for retrieval latency
- [ ] Add metrics for storage operations (Redis or Firestore)
- [ ] Add error rate tracking
- [ ] Set up alerts

### Deployment

**Interim (Redis)**:

- [ ] Verify Redis connection in production
- [ ] Deploy to staging
- [ ] Run smoke tests
- [ ] Gradual rollout to production
- [ ] Monitor metrics

**Production (Firestore)** - When available:

- [ ] Create Firestore indexes in production
- [ ] Configure Firestore environment variables
- [ ] Implement Firestore storage service (if not already done)
- [ ] Test Firestore implementation
- [ ] Migrate data from Redis to Firestore (optional)
- [ ] Switch to Firestore via configuration flag
- [ ] Monitor Firestore performance

## Post-Deployment

- [ ] Monitor error rates
- [ ] Monitor performance metrics
- [ ] Collect user feedback
- [ ] Plan optimizations based on usage patterns
- [ ] Document lessons learned

## Rollback Plan

- [ ] Document rollback procedure
- [ ] Test rollback in staging
- [ ] Keep previous version available
- [ ] Monitor for issues requiring rollback

---

## Notes

- Mark items as complete as you implement them
- Add notes for any deviations from the plan
- Update checklist if new requirements emerge
- Review with team before starting each phase
