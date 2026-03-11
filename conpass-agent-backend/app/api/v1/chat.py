from app.core.logging_config import get_logger


from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Request,
    status,
)

from app.services.chatbot.events import EventCallbackHandler
from app.schemas.chat import ChatData
from app.services.chatbot.vercel_response import VercelStreamResponse
from app.services.chatbot.engine import get_chat_engine
from app.services.conpass_api_service import get_conpass_api_service
from app.services.user_service import get_user_id_from_token
from app.services.chat_history.storage_factory import get_chat_history_storage
# from app.services.chatbot.query_filter import generate_filters

# import llama_index.core

# llama_index.core.set_global_handler("simple")


chat_router = r = APIRouter()

logger = get_logger(__name__)


@r.post(
    "",
    summary="Streaming Chat",
    description="Send a chat message and receive streaming responses",
    response_description="Server-sent events stream with chat responses and source citations",
    tags=["chat"],
)
async def chat(
    request: Request,
    data: ChatData,
    background_tasks: BackgroundTasks,
):
    """
    Real-Time Streaming Chat Endpoint (Server-Sent Events).
    Supports continuing existing chats via chat_id in data.data.chat_id.
    """
    try:
        # Middleware populates request.state.conpass_token after basic validation.
        conpass_jwt = getattr(request.state, "conpass_token", None)
        if not conpass_jwt:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing ConPass authentication token.",
            )

        scope = getattr(request.state, "scope", None)
        if scope != "write:chatbot":
            raise HTTPException(status_code=403, detail="Insufficient scope")

        # Extract user_id
        user_id = await get_user_id_from_token(conpass_jwt)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to retrieve user information.",
            )

        # Check if continuing an existing chat
        chat_id = data.data.chat_id if data.data else None
        storage = get_chat_history_storage()

        # If chat_id provided, load existing chat and merge messages
        if chat_id:
            try:
                existing_chat = await storage.get_chat(
                    user_id=user_id, chat_id=chat_id, format="chatdata"
                )
                # Verify ownership
                if existing_chat.user_id != user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have access to this chat.",
                    )

                # Convert existing messages to ChatMessage format and prepend to current messages
                from app.schemas.chat import Message, Annotation

                existing_messages = []
                for msg in existing_chat.messages:
                    # Convert ChatMessageHistory to Message
                    annotations = None
                    if msg.annotations:
                        annotations = [
                            Annotation(**ann) if isinstance(ann, dict) else ann
                            for ann in msg.annotations
                        ]

                    existing_messages.append(
                        Message(
                            role=msg.role,
                            content=msg.content,
                            annotations=annotations,
                        )
                    )

                # Prepend existing messages to current messages
                data.messages = existing_messages + data.messages
                logger.info(
                    f"Continuing chat {chat_id} with {len(existing_messages)} existing messages"
                )
            except ValueError:
                # Chat not found, treat as new chat
                logger.warning(f"Chat {chat_id} not found, creating new chat")
                chat_id = None

        last_message_content = data.get_last_message_content()
        messages = data.get_history_messages(include_agent_messages=True)
        session_type = data.get_session_type()

        logger.info("Received chat message for streaming endpoint")

        conpass_service = get_conpass_api_service(conpass_jwt)
        allowed_directory_ids = await conpass_service.get_allowed_directories()

        if not allowed_directory_ids:
            logger.warning("User does not have access to any directories!")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to any directories!",
            )
        # doc_ids = data.get_chat_document_ids()
        # filters = generate_filters(doc_ids)
        # index = get_index()
        # params = data.data or {}

        last_message_role = data.messages[-1].role
        event_handler = EventCallbackHandler()
        chat_engine = get_chat_engine(
            directory_ids=allowed_directory_ids,
            conpass_api_service=conpass_service,
            session_type=session_type,
            event_handlers=[event_handler],
            role = last_message_role,
        )

        response = chat_engine.astream_chat(last_message_content, chat_history=messages)
        # Pass chat_id to response handler for saving messages
        return VercelStreamResponse(
            request,
            event_handler,
            response,
            data,
            background_tasks,
            user_id=user_id,
            chat_id=chat_id,
            storage=storage,
        )
    except Exception as e:
        logger.exception("Error in chat engine", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in chat engine: {e}",
        ) from e
