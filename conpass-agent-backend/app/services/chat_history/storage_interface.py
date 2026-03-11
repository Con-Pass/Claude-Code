from abc import ABC, abstractmethod
from typing import List, Literal, Optional
from app.schemas.chat_history import (
    ChatSession,
    ChatSessionDetail,
    ChatSessionPayload,
    ChatHistoryList,
)
from app.schemas.chat import SessionType, Message


class ChatHistoryStorage(ABC):
    """Abstract interface for chat history storage"""

    @abstractmethod
    async def create_chat(
        self,
        user_id: str,
        session_type: SessionType,
        title: Optional[str] = None,
    ) -> ChatSession:
        """
        Create a new chat session.

        Args:
            user_id: User ID
            session_type: Type of session (conpass-only or general)
            title: Optional title (auto-generated if not provided)

        Returns:
            ChatSession with generated chat_id
        """
        pass

    @abstractmethod
    async def get_chat(
        self,
        user_id: str,
        chat_id: str,
        format: Literal["chatdata", "payload"] = "payload",
    ) -> ChatSessionDetail | ChatSessionPayload:
        """
        Get a chat session with messages.

        Args:
            user_id: User ID
            chat_id: Chat ID
            format: "chatdata" for internal format, "payload" for client format

        Returns:
            ChatSessionDetail or ChatSessionPayload
        """
        pass

    @abstractmethod
    async def list_chats(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        session_type: Optional[SessionType] = None,
    ) -> ChatHistoryList:
        """
        List chat sessions for a user.

        Args:
            user_id: User ID
            page: Page number (1-indexed)
            page_size: Number of items per page
            session_type: Optional filter by session type

        Returns:
            ChatHistoryList with paginated results
        """
        pass

    @abstractmethod
    async def add_messages(
        self,
        user_id: str,
        chat_id: str,
        messages_chatdata: List[Message],  # ChatData format
        messages_payload: List[dict],  # Client payload format
    ) -> None:
        """
        Add messages to an existing chat session.
        Stores messages in both formats (ChatData and client payload).

        Args:
            user_id: User ID
            chat_id: Chat ID
            messages_chatdata: Messages in ChatData format
            messages_payload: Messages in client payload format
        """
        pass

    @abstractmethod
    async def delete_chat(self, user_id: str, chat_id: str) -> None:
        """
        Delete a chat session and all its messages.

        Args:
            user_id: User ID
            chat_id: Chat ID
        """
        pass
