from typing import Optional
from app.core.logging_config import get_logger
from app.services.chat_history.storage_interface import ChatHistoryStorage
from app.services.chat_history.firestore_storage import FirestoreChatHistoryStorage

logger = get_logger(__name__)

# Singleton storage instance
_storage_instance: Optional[ChatHistoryStorage] = None


def get_chat_history_storage() -> ChatHistoryStorage:
    """
    Get the chat history storage instance.
    Uses Firestore as the storage backend.
    """
    global _storage_instance

    if _storage_instance is None:
        _storage_instance = FirestoreChatHistoryStorage()
        logger.info("Initialized Firestore chat history storage")

    return _storage_instance
