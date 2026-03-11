from app.core.logging_config import get_logger

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.chat_config import ChatConfig

config_router = r = APIRouter()

logger = get_logger(__name__)


@r.get(
    "",
    summary="Get Chat Configuration",
    description="Retrieve chat configuration including starter questions",
    response_description="Chat configuration with conversation starters",
    response_model=ChatConfig,
    tags=["config"],
)
async def chat_config() -> ChatConfig:
    """
    Get the current chat configuration.

    This endpoint returns:
    - Conversation starter questions
    - System configuration
    - UI hints and suggestions

    **Response:**
    - `starter_questions`: Array of suggested conversation starters

    **Use Case:**
    - Initialize chat UI with suggested questions
    - Display conversation starters to users
    - Provide context-aware prompts

    **Example Response:**
    ```json
    {
        "starter_questions": [
            "What is the main topic of this document?",
            "Can you summarize the key points?",
            "What are the important dates mentioned?"
        ]
    }
    ```
    """
    starter_questions = None
    conversation_starters = settings.CONVERSATION_STARTERS
    if conversation_starters and conversation_starters.strip():
        starter_questions = conversation_starters.strip().split("\n")
    return ChatConfig(starter_questions=starter_questions)
