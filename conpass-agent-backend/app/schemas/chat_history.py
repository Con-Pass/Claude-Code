from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from llama_index.core.llms import MessageRole
from app.schemas.chat import Annotation, SessionData, SessionType


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
    created_at: Optional[datetime] = None


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
