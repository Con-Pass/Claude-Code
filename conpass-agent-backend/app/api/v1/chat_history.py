from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Request, status, Query
from app.core.logging_config import get_logger
from app.services.user_service import get_user_id_from_token
from app.services.chat_history.storage_factory import get_chat_history_storage
from app.schemas.chat_history import ChatHistoryList, ChatPayloadFormat
from app.schemas.chat import SessionType

chat_history_router = r = APIRouter()
logger = get_logger(__name__)


@r.get(
    "/history",
    summary="List Chat History",
    description="Get a paginated list of chat sessions for the authenticated user",
    response_description="List of chat sessions with metadata",
    tags=["chat"],
)
async def list_chat_history(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    session_type: Optional[SessionType] = Query(
        None, description="Filter by session type (conpass-only or general)"
    ),
) -> ChatHistoryList:
    """
    List chat sessions for the authenticated user.
    """
    try:
        # Extract user_id from JWT token
        conpass_jwt = getattr(request.state, "conpass_token", None)
        if not conpass_jwt:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing ConPass authentication token.",
            )

        user_id = await get_user_id_from_token(conpass_jwt)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to retrieve user information.",
            )

        # Get storage and list chats
        storage = get_chat_history_storage()
        result = await storage.list_chats(
            user_id=user_id,
            page=page,
            page_size=page_size,
            session_type=session_type,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error listing chat history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing chat history: {str(e)}",
        ) from e


@r.get(
    "/{chat_id}",
    summary="Get Chat Details",
    description="Get full chat session with messages in client payload format (default) or internal chatdata format.",
    response_description="Chat session with messages",
    tags=["chat"],
)
async def get_chat(
    request: Request,
    chat_id: str,
    format: Literal["payload", "chatdata"] = Query(
        "payload",
        pattern="^(payload|chatdata)$",
        description="Message format: 'payload' (default, client payload format) or 'chatdata' (internal format).",
    ),
) -> ChatPayloadFormat:
    """
    Get a chat session with all messages in client payload format.
    """
    try:
        # Extract user_id from JWT token
        conpass_jwt = getattr(request.state, "conpass_token", None)
        if not conpass_jwt:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing ConPass authentication token.",
            )

        user_id = await get_user_id_from_token(conpass_jwt)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to retrieve user information.",
            )

        # Get storage and fetch chat
        storage = get_chat_history_storage()
        try:
            chat_session = await storage.get_chat(
                user_id=user_id,
                chat_id=chat_id,
                format=format,  # 'payload' or 'chatdata'
            )
        except ValueError as e:
            # Chat not found
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e

        # Verify ownership (already done by storage, but double-check)
        if chat_session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this chat.",
            )

        # Convert to client payload-style response.
        # For 'payload' format, messages are already in client payload format.
        # For 'chatdata' format, convert internal history messages to payload shape.
        from app.schemas.chat import SessionData

        if format == "payload":
            messages = chat_session.messages
        else:
            # chat_session is ChatSessionDetail with ChatMessageHistory messages
            messages = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "annotations": msg.annotations,
                    "parts": None,
                }
                for msg in chat_session.messages
            ]

        return ChatPayloadFormat(
            id=chat_session.id,
            messages=messages,
            data=SessionData(
                type=chat_session.session_type,
                chat_id=chat_session.id,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting chat {chat_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting chat: {str(e)}",
        ) from e


@r.delete(
    "/{chat_id}",
    summary="Delete Chat",
    description="Delete a chat session and all its messages",
    response_description="Success confirmation",
    tags=["chat"],
)
async def delete_chat(
    request: Request,
    chat_id: str,
) -> dict:
    """
    Delete a chat session and all its messages.
    """
    try:
        # Extract user_id from JWT token
        conpass_jwt = getattr(request.state, "conpass_token", None)
        if not conpass_jwt:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing ConPass authentication token.",
            )

        user_id = await get_user_id_from_token(conpass_jwt)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to retrieve user information.",
            )

        # Get storage and delete chat
        storage = get_chat_history_storage()
        try:
            # First verify chat exists and belongs to user
            chat_session = await storage.get_chat(
                user_id=user_id, chat_id=chat_id, format="payload"
            )
            if chat_session.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this chat.",
                )
        except ValueError:
            # Chat not found
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat {chat_id} not found.",
            )

        # Delete the chat
        await storage.delete_chat(user_id=user_id, chat_id=chat_id)

        return {"message": "Chat deleted successfully", "chat_id": chat_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting chat {chat_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting chat: {str(e)}",
        ) from e
