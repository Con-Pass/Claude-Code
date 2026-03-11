from app.core.logging_config import get_logger


from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Response,
    status,
)
from llama_index.core.llms import MessageRole

from app.schemas.chat import ChatData, Message, Result, SourceNodes
from app.services.chatbot.engine import get_chat_engine

# from app.services.chatbot.query_filter import generate_filters
from app.services.conpass_api_service import get_conpass_api_service
# import llama_index.core

# llama_index.core.set_global_handler("simple")


chat_non_streaming_router = r = APIRouter()

logger = get_logger(__name__)


@r.post(
    "",
    summary="Non-Streaming Chat",
    description="Send a chat message and receive a complete response",
    response_description="Complete chat response with sources",
    response_model=Result,
    tags=["chat"],
)
async def chat(
    request: Request,
    response: Response,
    data: ChatData,
) -> Result:
    """
    Get a complete chat response without streaming.
    """
    last_message_content = data.get_last_message_content()
    messages = data.get_history_messages()
    session_type = data.get_session_type()
    # doc_ids = data.get_chat_document_ids()
    # filters = generate_filters(doc_ids)

    conpass_jwt = getattr(request.state, "conpass_token", None)

    if not conpass_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing ConPass authentication token.",
        )

    logger.info(f"Using ConPass auth token for non-streaming chat request: '{last_message_content[:100]}'")

    # params = data.data or {}

    conpass_service = get_conpass_api_service(conpass_jwt)
    allowed_directory_ids = await conpass_service.get_allowed_directories()

    if not allowed_directory_ids:
        logger.warning("User does not have access to any directories!")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to any directories!",
        )

    chat_engine = get_chat_engine(
        directory_ids=allowed_directory_ids,
        conpass_api_service=conpass_service,
        session_type=session_type,
    )

    chat_response = await chat_engine.achat(last_message_content, messages)

    return Result(
        result=Message(role=MessageRole.ASSISTANT, content=chat_response.response),
        nodes=SourceNodes.from_source_nodes(chat_response.source_nodes),
    )
