from typing import List
from app.core.logging_config import get_logger
from app.schemas.chat import Message
from app.services.chat_history.storage_interface import ChatHistoryStorage

logger = get_logger(__name__)


async def save_chat_messages(
    storage: ChatHistoryStorage,
    user_id: str,
    chat_id: str,
    messages_chatdata: List[Message],
    messages_payload: List[dict],
) -> None:
    """
    Persist chat messages to storage for an **existing** chat session.

    This helper assumes that the chat session has already been created and identified
    by ``chat_id``. It is typically invoked as a FastAPI background task after the
    streaming response has been sent (or while it is in progress).

    Args:
        storage: Storage service instance.
        user_id: User ID.
        chat_id: Existing chat ID (must refer to a previously created session).
        messages_chatdata: Messages in internal ChatData format.
        messages_payload: Messages in client payload format.
    """
    try:
        if not messages_chatdata or not messages_payload:
            # Nothing to save
            return

        await storage.add_messages(
            user_id=user_id,
            chat_id=chat_id,
            messages_chatdata=messages_chatdata,
            messages_payload=messages_payload,
        )
        logger.info(f"Saved {len(messages_chatdata)} messages to chat {chat_id}")

    except Exception as e:
        # Log error but don't fail the chat request
        logger.exception(f"Error saving chat messages: {e}")
