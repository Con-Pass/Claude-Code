# Chat History Architecture & Implementation Plan

## Overview

This document outlines the architecture and implementation plan for chat history functionality, enabling users to view, continue, and delete their conversation history.

**Storage Backend**: The architecture uses an abstraction layer supporting both:

- **Redis** (Interim solution) - Already configured, allows immediate development
- **Firestore** (Production target) - Will be used once database access is available

See `CHAT_HISTORY_INTERIM_STORAGE.md` for Redis implementation details.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Data Models](#data-models)
3. [API Endpoints](#api-endpoints)
4. [Implementation Components](#implementation-components)
5. [Edge Cases & Error Handling](#edge-cases-error-handling)
6. [Security Considerations](#security-considerations)
7. [Performance Considerations](#performance-considerations)
8. [Migration Strategy](#migration-strategy)

---

## Architecture Overview

### High-Level Flow

```text
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       │ 1. POST /v1/chat (with chat_id or new)
       ▼
┌─────────────────────────────────────┐
│      Chat Endpoint                   │
│  - Extract user_id from JWT          │
│  - Load/create chat session          │
│  - Stream response                   │
│  - Save messages to storage         │
└──────┬───────────────────────────────┘
       │
       │ 2. Save messages
       ▼
┌─────────────────────────────────────┐
│   Storage Service (Abstraction)      │
│  - Redis (interim) or Firestore     │
│  - chat_sessions_chatdata           │
│  - chat_sessions_payload            │
└─────────────────────────────────────┘

┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       │ 3. GET /v1/chat/history
       ▼
┌─────────────────────────────────────┐
│   History Endpoint                   │
│  - List user's chats                 │
│  - Return metadata only              │
└─────────────────────────────────────┘

┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       │ 4. GET /v1/chat/{chat_id}
       ▼
┌─────────────────────────────────────┐
│   Get Chat Endpoint                  │
│  - Load full chat with messages      │
│  - Return in client payload format   │
└─────────────────────────────────────┘

┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       │ 5. DELETE /v1/chat/{chat_id}
       ▼
┌─────────────────────────────────────┐
│   Delete Chat Endpoint               │
│  - Verify ownership                  │
│  - Delete chat + messages            │
└─────────────────────────────────────┘
```

### Key Design Decisions

1. **User Identification**: Extract user ID from JWT token via ConPass API `/user` endpoint
2. **Storage**: Abstraction layer supporting Redis (interim) and Firestore (production) with separate storage for each format
3. **Streaming Compatibility**: Save messages after streaming completes (background task)
4. **Dual Format Storage**: Store messages in BOTH formats:
   - **ChatData format**: For internal use, compatibility with existing code, and processing
   - **Client payload format**: For easy round-trip with client, preserving `parts` field and exact structure
5. **Session Continuity**: Support continuing existing chats via `chat_id` parameter

---

## Data Models

### Storage Structure

**Separate Storage for Testing**: Store each format separately to enable A/B testing and easy removal of the unused format later.

**Interim Solution (Redis)**:

```text
Key Pattern: chat_sessions_chatdata:{user_id}:{chat_id} (Hash - ChatData format)
Key Pattern: chat_sessions_payload:{user_id}:{chat_id} (Hash - Client payload format)
Key Pattern: chat_list:{user_id} (Sorted Set - for pagination)

Hash Structure (chat_sessions_chatdata:user_123:chat_456):
  ├── id: string
  ├── user_id: string
  ├── title: string
  ├── session_type: "conpass-only" | "general"
  ├── created_at: timestamp (as string)
  ├── updated_at: timestamp (as string)
  ├── last_message_preview: string
  ├── message_count: number (as string)
  └── messages: JSON string (array of Message objects - no parts field)
```

**Production Solution (Firestore)** - When available:

```text
Collection: chat_sessions_chatdata (ChatData format - for internal processing)
/users/{user_id}/chats/{chat_id}
  ├── id: string (auto-generated)
  ├── user_id: string
  ├── title: string (auto-generated from first message or user-provided)
  ├── session_type: "conpass-only" | "general"
  ├── created_at: timestamp
  ├── updated_at: timestamp
  ├── last_message_preview: string (first 100 chars of last message)
  ├── message_count: number
  └── messages: array
      └── [Message objects compatible with ChatData schema - no parts field]

Collection: chat_sessions_payload (Client payload format - for round-trip)
/users/{user_id}/chats/{chat_id}
  ├── id: string (auto-generated)
  ├── user_id: string
  ├── title: string (auto-generated from first message or user-provided)
  ├── session_type: "conpass-only" | "general"
  ├── created_at: timestamp
  ├── updated_at: timestamp
  ├── last_message_preview: string (first 100 chars of last message)
  ├── message_count: number
  └── messages: array
      └── [Message objects with parts field, exact client format]
```

**Benefits of Separate Storage (Redis keys or Firestore collections):**

1. **Easy Testing**: Can test both formats independently
2. **Easy Cleanup**: Simply delete the unused collection after testing
3. **No Data Mixing**: Clear separation prevents confusion
4. **Independent Scaling**: Can optimize each collection separately
5. **Gradual Migration**: Can migrate from one to the other gradually

**Migration Strategy:**

- Phase 1: Write to both formats simultaneously (Redis keys or Firestore collections)
- Phase 2: Test both formats in production
- Phase 3: Decide which format works better
- Phase 4: Remove the unused format and update code to use only the chosen format
- Phase 5: **When Firestore available**: Migrate from Redis to Firestore (optional)

### Pydantic Schemas

**Dual Format Support**: Schemas support both ChatData format (for internal use) and client payload format (for round-trip).

```python
# app/schemas/chat_history.py

class MessagePart(BaseModel):
    """Message part structure (from client payload)"""
    type: str  # e.g., "text"
    text: str

class ChatMessageHistory(BaseModel):
    """Stored message in ChatData format (for internal processing)"""
    id: Optional[str] = None
    role: MessageRole
    content: str
    annotations: List[Annotation] | None = None
    created_at: datetime
    order: int

class ChatMessagePayload(BaseModel):
    """Stored message in client payload format (for round-trip)"""
    role: MessageRole
    content: str
    annotations: List[Annotation] | None = None
    parts: List[MessagePart] | None = None  # Client payload format

class ChatSession(BaseModel):
    """Chat session metadata"""
    id: str
    user_id: str
    title: str
    session_type: SessionType
    created_at: datetime
    updated_at: datetime
    last_message_preview: str
    message_count: int

class ChatSessionDetail(ChatSession):
    """Full chat session with messages in ChatData format"""
    messages: List[ChatMessageHistory]  # ChatData format

class ChatSessionPayload(ChatSession):
    """Full chat session with messages in client payload format"""
    messages: List[ChatMessagePayload]  # Client payload format

class ChatPayloadFormat(BaseModel):
    """Client payload format - exact format for round-trip"""
    id: str  # chat_id
    messages: List[ChatMessagePayload]  # Client payload format
    data: SessionData  # Contains type and optionally chat_id

class ChatHistoryList(BaseModel):
    """List of chat sessions"""
    chats: List[ChatSession]
    total: int
    page: int
    page_size: int

class CreateChatRequest(BaseModel):
    """Request to create a new chat"""
    title: Optional[str] = None  # Auto-generate if not provided
    session_type: SessionType

class ContinueChatRequest(BaseModel):
    """Request to continue existing chat"""
    chat_id: str
```

---

## API Endpoints

### 1. Create/Continue Chat (Modified Existing Endpoint)

**Endpoint**: `POST /v1/chat`

**Request Body** (Extended `ChatData`):

```json
{
  "messages": [...],
  "data": {
    "type": "conpass-only",
    "chat_id": "optional-existing-chat-id"  // NEW
  }
}
```

**Response**: Streaming response (unchanged)

**Behavior**:

- If `chat_id` provided: Load existing chat, append new messages
- If no `chat_id`: Create new chat session
- Save all messages to Firestore after streaming completes (background task)

### 2. List Chat History

**Endpoint**: `GET /v1/chat/history`

**Query Parameters**:

- `page`: int = 1 (pagination)
- `page_size`: int = 20 (max 100)
- `session_type`: Optional["conpass-only" | "general"] (filter)

**Response**:

```json
{
  "chats": [
    {
      "id": "chat_123",
      "title": "Contract Analysis",
      "session_type": "conpass-only",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T11:45:00Z",
      "last_message_preview": "Based on the contracts I found...",
      "message_count": 12
    }
  ],
  "total": 45,
  "page": 1,
  "page_size": 20
}
```

### 3. Get Chat Details

**Endpoint**: `GET /v1/chat/{chat_id}`

**Response**: Returns the chat in the exact same format as the client payload:

```json
{
  "id": "qsDYXHQWtaWac2YM",
  "messages": [
    {
      "role": "user",
      "content": "雇用契約書の対象者と更新期限を一覧化して？",
      "parts": [
        {
          "type": "text",
          "text": "雇用契約書の対象者と更新期限を一覧化して？"
        }
      ],
      "annotations": null
    },
    {
      "role": "assistant",
      "content": "## 雇用契約書の対象者と更新期限一覧\n\n...",
      "annotations": [
        {
          "type": "events",
          "data": {"title": "🔧 Processing: metadata_search"}
        },
        {
          "type": "sources",
          "data": {"nodes": []}
        },
        {
          "type": "tools",
          "data": {
            "toolOutput": {...},
            "toolCall": {...}
          }
        }
      ],
      "parts": [
        {
          "type": "text",
          "text": "## 雇用契約書の対象者と更新期限一覧\n\n..."
        }
      ]
    }
  ],
  "data": {
    "type": "general"
  }
}
```

**Note**: This format matches exactly what the client sends, making it easy to continue the conversation by passing this payload back to `POST /v1/chat`. The service maintains messages in both ChatData format (for internal processing) and client payload format (for round-trip compatibility).

**Note**: This format matches exactly what the client sends, making it easy to continue the conversation by passing this payload back to `POST /v1/chat`.

**Error Cases**:

- 404: Chat not found
- 403: Chat belongs to different user

### 4. Delete Chat

**Endpoint**: `DELETE /v1/chat/{chat_id}`

**Response**: `204 No Content`

**Behavior**:

- Deletes chat from both storage locations (Redis keys or Firestore collections: `chat_sessions_chatdata` and `chat_sessions_payload`)

**Error Cases**:

- 404: Chat not found
- 403: Chat belongs to different user

## Implementation Components

### 1. User ID Extraction Service

**File**: `app/services/user_service.py`

```python
class UserService:
    """Service to extract user information from JWT token"""
    
    @staticmethod
    async def get_user_id_from_token(conpass_jwt: str) -> str:
        """
        Extract user ID from ConPass API using JWT token.
        Returns user ID or raises exception.
        """
        # Call ConPass API /user endpoint
        # Extract user ID from response
        # Cache result if needed
```

**Integration Point**:

- Modify `chat.py` endpoint to extract user_id
- Store in `request.state.user_id` for downstream use

### 2. Storage Service (Abstraction Layer)

**File**: `app/services/chat_history/storage_interface.py` (abstract interface)
**File**: `app/services/chat_history/redis_storage.py` (Redis implementation - interim)
**File**: `app/services/chat_history/firestore_storage.py` (Firestore implementation - when ready)
**File**: `app/services/chat_history/storage_factory.py` (factory to select implementation)

```python
# Abstract Interface
from abc import ABC, abstractmethod

class ChatHistoryStorage(ABC):
    """Abstract interface for chat history storage"""
    
    @abstractmethod
    async def create_chat(
        self, 
        user_id: str, 
        session_type: SessionType,
        title: Optional[str] = None
    ) -> ChatSession:
        pass
    
    @abstractmethod
    async def get_chat(
        self, 
        user_id: str, 
        chat_id: str,
        format: Literal["chatdata", "payload"] = "payload"
    ) -> ChatSessionDetail | ChatSessionPayload:
        pass
    
    @abstractmethod
    async def list_chats(
        self, 
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        session_type: Optional[SessionType] = None
    ) -> ChatHistoryList:
        pass
    
    @abstractmethod
    async def add_messages(
        self,
        user_id: str,
        chat_id: str,
        messages_chatdata: List[Message],
        messages_payload: List[dict]
    ) -> None:
        pass
    
    @abstractmethod
    async def delete_chat(self, user_id: str, chat_id: str) -> None:
        pass

# Redis Implementation (Interim)
class RedisChatHistoryStorage(ChatHistoryStorage):
    """Redis implementation - used until Firestore is available"""
    # Uses Redis hashes and sorted sets
    # See CHAT_HISTORY_INTERIM_STORAGE.md for details

# Firestore Implementation (Production)
class FirestoreChatHistoryStorage(ChatHistoryStorage):
    """Firestore implementation - production target"""
    
    async def create_chat(
        self, 
        user_id: str, 
        session_type: SessionType,
        title: Optional[str] = None
    ) -> ChatSession
    
    async def get_chat(
        self, 
        user_id: str, 
        chat_id: str,
        format: Literal["chatdata", "payload"] = "payload"
    ) -> ChatSessionDetail | ChatSessionPayload
    
    async def get_chat_payload_format(
        self,
        user_id: str,
        chat_id: str
    ) -> ChatPayloadFormat
    
    async def list_chats(
        self, 
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        session_type: Optional[SessionType] = None
    ) -> ChatHistoryList
    
    async def add_messages(
        self,
        user_id: str,
        chat_id: str,
        messages_chatdata: List[Message],  # ChatData format
        messages_payload: List[dict]  # Client payload format
    ) -> None:
        """
        Save messages to both storage locations (Redis keys or Firestore collections):
        - chat_sessions_chatdata: For internal processing
        - chat_sessions_payload: For client round-trip
        """
    
    async def delete_chat(self, user_id: str, chat_id: str) -> None:
        """
        Delete chat from both storage locations (Redis keys or Firestore collections):
        - chat_sessions_chatdata
        - chat_sessions_payload
        """
```

**Storage Configuration**:

**Interim Solution (Redis)**:

- **Key Pattern 1**: `chat_sessions_chatdata:{user_id}:{chat_id}` (Hash - ChatData format)
- **Key Pattern 2**: `chat_sessions_payload:{user_id}:{chat_id}` (Hash - Client payload format)
- **Key Pattern 3**: `chat_list:{user_id}` (Sorted Set - for pagination)
- Uses existing `REDIS_URL` configuration
- No additional setup required

**Production Solution (Firestore)** - When available:

- **Collection 1**: `chat_sessions_chatdata` (ChatData format)
  - Document structure: `/users/{user_id}/chats/{chat_id}`
  - Used for: Internal processing, existing code compatibility
  
- **Collection 2**: `chat_sessions_payload` (Client payload format)
  - Document structure: `/users/{user_id}/chats/{chat_id}`
  - Used for: Client round-trip, API responses

- **Indexes required** (for both collections):
  - `user_id` + `updated_at` (descending) for list queries
  - `user_id` + `session_type` + `updated_at` (descending) for filtered queries

**Note**: After testing, one collection will be removed. Both collections use the same structure and indexes for consistency. The abstraction layer allows switching from Redis to Firestore with zero code changes.

### 3. Chat History API Endpoints

**File**: `app/api/v1/chat_history.py`

```python
@router.get("/history")
async def list_chat_history(...) -> ChatHistoryList

@router.get("/{chat_id}")
async def get_chat(...) -> ChatPayloadFormat  # Returns client payload format

@router.delete("/{chat_id}")
async def delete_chat(...) -> Response
```

### 4. Modified Chat Endpoint

**File**: `app/api/v1/chat.py` (modifications)

**Changes**:

1. Extract `user_id` from JWT token
2. Check for `chat_id` in request `data`
3. Load existing chat if `chat_id` provided
4. Merge existing messages with new messages
5. Save messages to Firestore after streaming (background task)

**Background Task**:

```python
async def save_chat_messages(
    user_id: str,
    chat_id: str,
    messages_chatdata: List[Message],  # ChatData format
    messages_payload: List[dict],  # Client payload format
    storage_service: ChatHistoryStorage  # Abstraction layer
):
    """
    Save messages to storage (Redis or Firestore) in both formats after streaming completes.
    - chat_sessions_chatdata: For internal processing
    - chat_sessions_payload: For client round-trip
    
    Uses abstraction layer - works with both Redis (interim) and Firestore (production).
    """
    try:
        await storage_service.add_messages(
            user_id, 
            chat_id, 
            messages_chatdata, 
            messages_payload
        )
    except Exception as e:
        logger.error(f"Failed to save chat messages: {e}")
```

### 5. Message Saving Integration

**File**: `app/services/chatbot/vercel_response.py` (modifications)

**Changes**:

- Add callback to save messages after streaming completes
- Track all messages (user + assistant) during streaming in both formats:
  - ChatData format: For internal processing and compatibility
  - Client payload format: For round-trip with client (includes `parts` field)
- Invoke background task to save both formats to Firestore

---

## Edge Cases & Error Handling {#edge-cases-error-handling}

### 1. User ID Extraction Failures

**Scenario**: ConPass API unavailable or returns error

**Handling**:

- Log error with context
- Return 503 Service Unavailable
- Do not proceed with chat (security requirement)

**Implementation**:

```python
try:
    user_id = await user_service.get_user_id_from_token(conpass_jwt)
except ConPassAPIError:
    raise HTTPException(503, "Authentication service unavailable")
```

### 2. Chat Not Found

**Scenario**: User provides invalid `chat_id` or chat belongs to different user

**Handling**:

- Verify chat exists and belongs to user
- Return 404 if not found
- Return 403 if belongs to different user

### 3. Concurrent Chat Updates

**Scenario**: Multiple requests try to update same chat simultaneously

**Handling**:

- Use Firestore transactions for message additions
- Last write wins for title updates (acceptable)
- Use optimistic locking if needed for critical updates

### 4. Firestore Write Failures

**Scenario**: Network issues or Firestore quota exceeded

**Handling**:

- Log error but don't fail chat request (chat works without history)
- Implement retry logic with exponential backoff
- Queue failed writes for later retry (optional)

### 5. Large Message History

**Scenario**: Chat has thousands of messages

**Handling**:

- Paginate message retrieval in `get_chat` endpoint
- Limit message count in list view
- Consider archiving old chats

### 6. Streaming Interruption

**Scenario**: Client disconnects during streaming

**Handling**:

- Save messages that were sent before disconnection
- Mark chat as incomplete (optional metadata field)
- Allow continuation on next request

### 7. Invalid Message Format

**Scenario**: Messages don't match expected schema

**Handling**:

- Validate messages before saving
- Log and skip invalid messages
- Continue with valid messages

### 8. Title Generation Failures

**Scenario**: Auto-title generation fails (e.g., empty first message)

**Handling**:

- Fallback to "Untitled Chat" or timestamp-based title

---

## Security Considerations

### 1. User Isolation

**Requirement**: Users can only access their own chats

**Implementation**:

- Always verify `user_id` matches chat owner
- Use Firestore security rules (if applicable)
- Server-side validation in all endpoints

**Firestore Rules** (if using client SDK):

```javascript
match /users/{userId}/chats/{chatId} {
  allow read, write: if request.auth != null && request.auth.uid == userId;
}
```

### 2. Input Validation

**Requirement**: Validate all inputs before processing

**Implementation**:

- Use Pydantic models for validation
- Sanitize user-provided titles
- Validate `chat_id` format (UUID or similar)
- Limit message content size (e.g., 1MB per message)

### 3. Rate Limiting

**Requirement**: Prevent abuse of chat history endpoints

**Implementation**:

- Rate limit per user_id
- Limit pagination page_size (max 100)
- Throttle Firestore writes

### 4. Data Privacy

**Requirement**: Protect sensitive chat data

**Implementation**:

- Encrypt sensitive fields if required
- Implement data retention policies
- Support chat deletion (GDPR compliance)
- Log access for audit trail

### 5. JWT Token Validation

**Requirement**: Ensure token is valid before processing

**Implementation**:

- Leverage existing middleware validation
- Verify token hasn't expired
- Check user still exists in ConPass system

---

## Performance Considerations

### 1. Firestore Queries

**Optimization**:

- Create composite indexes for common queries
- Use pagination to limit document reads
- Cache frequently accessed chats (Redis for caching)
- Use batch operations for multiple writes (Redis pipeline or Firestore batch)

**Indexes Required**:

**Interim (Redis)**: No indexes needed! Uses sorted sets for pagination.

**Production (Firestore)** - When available:

```text
Collection: chat_sessions_chatdata
- user_id (ASC) + updated_at (DESC)
- user_id (ASC) + session_type (ASC) + updated_at (DESC)

Collection: chat_sessions_payload
- user_id (ASC) + updated_at (DESC)
- user_id (ASC) + session_type (ASC) + updated_at (DESC)
```

### 2. Message Loading

**Optimization**:

- Lazy load messages (only when `get_chat` called)
- Paginate messages in detail view
- Stream messages for very large chats

### 3. Background Tasks

**Optimization**:

- Use async background tasks (FastAPI BackgroundTasks)
- Batch message writes (Firestore batch limit: 500)
- Implement retry queue for failed writes

### 4. Caching Strategy

**Cache Layers**:

1. **User ID Cache**: Cache user_id from JWT (TTL: 5 minutes)
2. **Chat List Cache**: Cache recent chat list (TTL: 1 minute)
3. **Chat Detail Cache**: Cache individual chats (TTL: 30 seconds)

**Cache Invalidation**:

- Invalidate on chat create/update/delete
- Use Redis for distributed caching

### 5. Database Connection Pooling

**Optimization**:

- Use Firestore client connection pooling
- Implement connection retry logic
- Monitor connection health

---

## Migration Strategy

**Storage Approach**:

- **Interim**: Use Redis with separate keys for each format (`chat_sessions_chatdata:{user_id}:{chat_id}` and `chat_sessions_payload:{user_id}:{chat_id}`)
- **Production**: Use Firestore with separate collections (`chat_sessions_chatdata` and `chat_sessions_payload`)

During implementation, we'll write to both formats in the chosen storage backend. After testing determines which format works better, we'll remove the unused format and update the code to use only the chosen format.

### Phase 1: Foundation (Week 1)

1. ✅ Set up storage abstraction layer (interface)
2. ✅ Create user service for ID extraction
3. ✅ Implement Redis storage service (interim solution)
4. ✅ Add Pydantic schemas for chat history
5. ✅ Write unit tests for Redis storage service
6. ⏳ **When Firestore available**: Implement Firestore storage service

### Phase 2: Core Functionality (Week 2)

1. ✅ Implement chat history API endpoints
2. ✅ Modify chat endpoint to support `chat_id`
3. ✅ Integrate message saving (background tasks)
4. ✅ Add error handling and validation
5. ✅ Write integration tests

### Phase 3: Edge Cases & Polish (Week 3)

1. ✅ Handle all edge cases
2. ✅ Implement caching
3. ✅ Add monitoring and logging
4. ✅ Performance optimization
5. ✅ Security audit

### Phase 4: Testing & Deployment (Week 4)

1. ✅ End-to-end testing with both formats (Redis)
2. ✅ Load testing both formats
3. ✅ Security testing
4. ✅ Documentation
5. ✅ Gradual rollout with Redis
6. ✅ Monitor both formats in production
7. ⏳ **When Firestore available**: Test Firestore implementation
8. ⏳ **When Firestore available**: Migrate data and switch

### Phase 5: Format Selection & Cleanup (Week 5)

1. ✅ Analyze performance of both formats
2. ✅ Decide which format works better
3. ✅ Update code to use only chosen format
4. ✅ Clean up unused format from storage
5. ✅ Update documentation

### Phase 6: Firestore Migration (When Available)

1. ⏳ Implement Firestore storage service
2. ⏳ Test Firestore implementation
3. ⏳ Migrate data from Redis to Firestore (optional)
4. ⏳ Switch to Firestore via configuration
5. ⏳ Monitor Firestore performance
6. ⏳ Deprecate Redis storage (optional)

### Backward Compatibility

**Strategy**:

- Make `chat_id` optional in existing endpoint
- Existing clients continue to work (no `chat_id` = new chat)
- No breaking changes to response format

---

## Testing Strategy

### Unit Tests

- User service (ID extraction)
- Firestore service (CRUD operations)
- Schema validation
- Error handling

### Integration Tests

- API endpoints with mock Firestore
- End-to-end chat flow with history
- Concurrent access scenarios
- Error recovery

### Load Tests

- Concurrent chat creation
- Large message history retrieval
- Firestore write performance
- Cache effectiveness

---

## Monitoring & Observability

### Metrics to Track

1. Chat creation rate
2. Chat retrieval latency
3. Firestore write success/failure rate
4. Cache hit rate
5. Error rates by type
6. User activity patterns

### Logging

- Chat creation/deletion events
- Firestore operation failures
- Authentication failures
- Performance bottlenecks

### Alerts

- Firestore quota approaching limit
- High error rate on writes
- Authentication service downtime
- Unusual access patterns

---

## Future Enhancements

1. **Chat Search**: Full-text search across chat history
2. **Chat Export**: Export chats as PDF/JSON
3. **Chat Sharing**: Share chats with other users (with permissions)
4. **Chat Templates**: Save and reuse chat templates
5. **Chat Analytics**: Usage analytics and insights
6. **Multi-device Sync**: Real-time sync across devices
7. **Chat Archiving**: Archive old chats to cold storage

---

## Dependencies

### Interim Solution (Redis)

**No new dependencies required!** Redis is already configured and available.

### Production Solution (Firestore)

**When Firestore access is available:**

```toml
google-cloud-firestore>=2.14.0  # Firestore client
```

### Configuration Required

**Interim (Redis)**: Uses existing `REDIS_URL` - no additional config needed!

**Production (Firestore)** - When available:

```python
# app/core/config.py
FIRESTORE_PROJECT_ID: str
FIRESTORE_CREDENTIALS_PATH: Optional[str] = None  # For local dev
FIRESTORE_DATABASE_ID: Optional[str] = None  # For Firestore Native mode
USE_FIRESTORE: bool = False  # Set to True when switching to Firestore
```

---

## File Structure

```text
app/
├── api/
│   └── v1/
│       ├── chat.py (modified)
│       └── chat_history.py (new)
├── schemas/
│   └── chat_history.py (new)
├── services/
│   ├── user_service.py (new)
│   └── chat_history/
│       ├── __init__.py
│       ├── storage_interface.py (new - abstract interface)
│       ├── redis_storage.py (new - interim implementation)
│       ├── firestore_storage.py (new - when Firestore available)
│       ├── storage_factory.py (new - selects implementation)
│       └── message_saver.py (new)
└── core/
    └── config.py (modified - add Firestore config)
```

---

## Conclusion

This architecture provides a robust, scalable, and secure foundation for chat history functionality. The design prioritizes:

1. **Security**: User isolation and input validation
2. **Performance**: Caching and optimized queries
3. **Reliability**: Error handling and retry logic
4. **Scalability**: Pagination and efficient data structures
5. **Maintainability**: Clear separation of concerns

The implementation follows industry best practices and handles edge cases comprehensively while maintaining backward compatibility with existing functionality.
