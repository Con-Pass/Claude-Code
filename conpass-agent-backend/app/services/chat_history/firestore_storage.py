import uuid
from datetime import datetime, timezone
from typing import List, Literal, Optional
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from app.core.logging_config import get_logger
from app.core.config import settings
from app.schemas.chat_history import (
    ChatSession,
    ChatSessionDetail,
    ChatSessionPayload,
    ChatHistoryList,
    ChatMessageHistory,
    ChatMessagePayload,
)
from app.schemas.chat import SessionType, Message, MessageRole
from app.services.chat_history.storage_interface import ChatHistoryStorage

logger = get_logger(__name__)


def get_firestore_client() -> firestore.Client:
    """
    Get Firestore client instance.
    Uses default credentials or service account file if specified.
    """
    try:
        client_options = {}
        if settings.FIRESTORE_DATABASE_ID:
            client_options["database"] = settings.FIRESTORE_DATABASE_ID

        # Use Application Default Credentials (ADC), configured via gcloud or
        # environment, for both local development and deployed environments.
        client = firestore.Client(
            project=settings.FIRESTORE_PROJECT_ID,
            **client_options,
        )

        return client
    except Exception as e:
        logger.error(f"Failed to initialize Firestore client: {e}")
        raise


def generate_chat_id() -> str:
    """Generate a unique chat ID"""
    return str(uuid.uuid4())


def generate_title_from_message(message_content: str) -> str:
    """Generate a title from the first message content"""
    if not message_content:
        return "New Chat"

    # Take first 50 characters and clean up
    title = message_content.strip()[:50]
    # Remove newlines and extra spaces
    title = " ".join(title.split())
    return title if title else "New Chat"


class FirestoreChatHistoryStorage(ChatHistoryStorage):
    """Firestore implementation of chat history storage"""

    def __init__(self):
        self.client = get_firestore_client()
        self.chatdata_collection = "chat_sessions_chatdata"
        self.payload_collection = "chat_sessions_payload"

    def _get_chatdata_ref(self, user_id: str, chat_id: str):
        """Get reference to chat document in chatdata collection"""
        # Use composite document ID: {user_id}_{chat_id} for easier querying
        doc_id = f"{user_id}_{chat_id}"
        return self.client.collection(self.chatdata_collection).document(doc_id)

    def _get_payload_ref(self, user_id: str, chat_id: str):
        """Get reference to chat document in payload collection"""
        # Use composite document ID: {user_id}_{chat_id} for easier querying
        doc_id = f"{user_id}_{chat_id}"
        return self.client.collection(self.payload_collection).document(doc_id)

    async def create_chat(
        self,
        user_id: str,
        session_type: SessionType,
        title: Optional[str] = None,
    ) -> ChatSession:
        """Create a new chat session"""
        chat_id = generate_chat_id()
        now = datetime.now(timezone.utc)

        if not title:
            title = "New Chat"

        # Create document data
        chat_data: dict = {
            "id": chat_id,
            "user_id": user_id,
            "title": title,
            "session_type": session_type.value,
            "created_at": now,
            "updated_at": now,
            "last_message_preview": "",
            "message_count": 0,
            "messages": [],
        }

        # Create in both collections atomically using batch
        batch = self.client.batch()
        chatdata_ref = self._get_chatdata_ref(user_id, chat_id)
        payload_ref = self._get_payload_ref(user_id, chat_id)

        batch.set(chatdata_ref, chat_data)
        batch.set(payload_ref, chat_data)
        batch.commit()

        logger.info(f"Created chat {chat_id} for user {user_id}")

        return ChatSession(
            id=chat_id,
            user_id=user_id,
            title=title,
            session_type=session_type,
            created_at=now,
            updated_at=now,
            last_message_preview="",
            message_count=0,
        )

    async def get_chat(
        self,
        user_id: str,
        chat_id: str,
        format: Literal["chatdata", "payload"] = "payload",
    ) -> ChatSessionDetail | ChatSessionPayload:
        """Get a chat session with messages"""
        # Choose the appropriate collection based on format
        if format == "chatdata":
            doc_ref = self._get_chatdata_ref(user_id, chat_id)
        else:
            doc_ref = self._get_payload_ref(user_id, chat_id)

        doc = doc_ref.get()
        if not doc.exists:
            raise ValueError(f"Chat {chat_id} not found for user {user_id}")

        data = doc.to_dict()
        if not data:
            raise ValueError(f"Chat {chat_id} has no data for user {user_id}")

        # Parse timestamps
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        if isinstance(created_at, datetime):
            # Already a datetime
            pass
        elif hasattr(created_at, "timestamp"):
            # Firestore timestamp
            created_at = created_at.to_datetime()
        else:
            created_at = datetime.now(timezone.utc)

        if isinstance(updated_at, datetime):
            # Already a datetime
            pass
        elif hasattr(updated_at, "timestamp"):
            # Firestore timestamp
            updated_at = updated_at.to_datetime()
        else:
            updated_at = datetime.now(timezone.utc)

        # Validate and convert session_type
        try:
            session_type_value = SessionType(data["session_type"])
        except ValueError:
            invalid_type = data.get("session_type", "unknown")
            raise ValueError(
                f"Chat {chat_id} has invalid session_type '{invalid_type}'. "
                f"Valid values are: {', '.join([st.value for st in SessionType])}"
            )

        # Build session
        session = ChatSession(
            id=data["id"],
            user_id=data["user_id"],
            title=data["title"],
            session_type=session_type_value,
            created_at=created_at,
            updated_at=updated_at,
            last_message_preview=data.get("last_message_preview", ""),
            message_count=data.get("message_count", 0),
        )

        # Convert messages based on format
        messages_data = data.get("messages", [])
        if format == "chatdata":
            messages = [
                ChatMessageHistory(
                    id=msg.get("id"),
                    role=MessageRole(msg["role"]),
                    content=msg["content"],
                    annotations=msg.get("annotations"),
                    created_at=msg.get("created_at", created_at)
                    if isinstance(msg.get("created_at"), datetime)
                    else datetime.fromisoformat(msg["created_at"])
                    if isinstance(msg.get("created_at"), str)
                    else created_at,
                    order=msg["order"],
                )
                for msg in messages_data
            ]
            return ChatSessionDetail(**session.model_dump(), messages=messages)
        else:
            messages = [
                ChatMessagePayload(  # type: ignore
                    role=MessageRole(msg["role"]),
                    content=msg["content"],
                    annotations=msg.get("annotations"),
                    parts=msg.get("parts"),
                    created_at=msg.get("created_at", created_at),
                )
                for msg in messages_data
            ]
            return ChatSessionPayload(**session.model_dump(), messages=messages)

    async def list_chats(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        session_type: Optional[SessionType] = None,
    ) -> ChatHistoryList:
        """List chat sessions for a user"""
        # Query payload collection for user's chats
        # Documents are stored with ID: {user_id}_{chat_id}
        # Start with base query
        query = self.client.collection(self.payload_collection).where(
            filter=FieldFilter("user_id", "==", user_id)
        )

        # Filter by session_type if specified
        # Note: If filtering by session_type, we need an index for (user_id, session_type, updated_at)
        # For now, we'll fetch all and filter/sort in memory to avoid index requirements
        if session_type:
            query = query.where(
                filter=FieldFilter("session_type", "==", session_type.value)
            )

        # Fetch all matching documents
        # Note: For production, create Firestore indexes for efficient querying
        all_docs = list(query.stream())

        # Convert to ChatSession and sort by updated_at
        all_chats = []
        for doc in all_docs:
            data = doc.to_dict()
            if not data:
                continue

            # Parse timestamps
            created_at = data.get("created_at")
            updated_at = data.get("updated_at")
            if hasattr(created_at, "to_datetime"):
                created_at = created_at.to_datetime()
            elif isinstance(created_at, datetime):
                pass
            else:
                created_at = datetime.now(timezone.utc)

            if hasattr(updated_at, "to_datetime"):
                updated_at = updated_at.to_datetime()
            elif isinstance(updated_at, datetime):
                pass
            else:
                updated_at = datetime.now(timezone.utc)

            # Validate and convert session_type
            # Skip documents with invalid session_type values (e.g., legacy "management" type)
            try:
                session_type_value = SessionType(data["session_type"])
            except ValueError:
                logger.warning(
                    f"Skipping chat {data.get('id', 'unknown')} with invalid session_type: {data.get('session_type')}"
                )
                continue

            chat = ChatSession(
                id=data["id"],
                user_id=data["user_id"],
                title=data["title"],
                session_type=session_type_value,
                created_at=created_at,
                updated_at=updated_at,
                last_message_preview=data.get("last_message_preview", ""),
                message_count=data.get("message_count", 0),
            )
            all_chats.append(chat)

        # Sort by updated_at descending
        all_chats.sort(key=lambda x: x.updated_at, reverse=True)

        # Paginate
        total = len(all_chats)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_chats = all_chats[start:end]

        return ChatHistoryList(
            chats=paginated_chats, total=total, page=page, page_size=page_size
        )

    async def add_messages(
        self,
        user_id: str,
        chat_id: str,
        messages_chatdata: List[Message],
        messages_payload: List[dict],
    ) -> None:
        """Add messages to an existing chat session"""
        # Get existing chat documents
        chatdata_ref = self._get_chatdata_ref(user_id, chat_id)
        payload_ref = self._get_payload_ref(user_id, chat_id)

        chatdata_doc = chatdata_ref.get()
        payload_doc = payload_ref.get()

        if not chatdata_doc.exists or not payload_doc.exists:
            raise ValueError(f"Chat {chat_id} not found for user {user_id}")

        chatdata_data = chatdata_doc.to_dict()
        payload_data = payload_doc.to_dict()

        existing_chatdata_messages = chatdata_data.get("messages", [])
        existing_payload_messages = payload_data.get("messages", [])

        # Convert new messages to storage format
        now = datetime.now(timezone.utc)

        # Add ChatData format messages
        for i, msg in enumerate(messages_chatdata):
            order = len(existing_chatdata_messages) + i
            msg_data = {
                "id": str(uuid.uuid4()),
                "role": msg.role.value,
                "content": msg.content,
                "annotations": (
                    [
                        ann.model_dump() if hasattr(ann, "model_dump") else ann
                        for ann in msg.annotations
                    ]
                    if msg.annotations
                    else None
                ),
                "created_at": now,
                "order": order,
            }
            existing_chatdata_messages.append(msg_data)

        # Add payload format messages
        for msg in messages_payload:
            if "created_at" not in msg:  # type: ignore
                msg["created_at"] = now  # type: ignore
            existing_payload_messages.append(msg)

        # Update last message preview
        last_message = messages_chatdata[-1] if messages_chatdata else None
        last_preview = ""
        if last_message:
            last_preview = last_message.content[:100]

        # Update both documents atomically
        batch = self.client.batch()
        batch.update(
            chatdata_ref,
            {
                "messages": existing_chatdata_messages,
                "updated_at": now,
                "last_message_preview": last_preview,
                "message_count": len(existing_chatdata_messages),
            },
        )
        batch.update(
            payload_ref,
            {
                "messages": existing_payload_messages,
                "updated_at": now,
                "last_message_preview": last_preview,
                "message_count": len(existing_payload_messages),
            },
        )
        batch.commit()

        logger.info(f"Added {len(messages_chatdata)} messages to chat {chat_id}")

    async def delete_chat(self, user_id: str, chat_id: str) -> None:
        """Delete a chat session and all its messages"""
        chatdata_ref = self._get_chatdata_ref(user_id, chat_id)
        payload_ref = self._get_payload_ref(user_id, chat_id)

        # Delete both documents
        batch = self.client.batch()
        batch.delete(chatdata_ref)
        batch.delete(payload_ref)
        batch.commit()

        logger.info(f"Deleted chat {chat_id} for user {user_id}")
