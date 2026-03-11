from typing import List, Optional
from llama_index.llms.openai import OpenAI
from app.core.config import settings
from app.core.logging_config import get_logger
import tiktoken
from llama_index.core.llms import ChatMessage

logger = get_logger(__name__)

MAX_TOKEN_COUNT = 40000
SUMMARY_MODEL = "gpt-4.1-nano"


async def summarize_conversation_history(
    chat_history: List[ChatMessage], max_messages: int = 20
) -> Optional[str]:
    """
    Create a fast, concise summary of recent conversation history if token count > 5000.
    Otherwise, return the conversation as-is.

    Args:
        chat_history: List of chat messages
        max_messages: Number of recent messages to summarize

    Returns:
        Brief conversation summary or original conversation string
    """
    if not chat_history:
        return None

    recent = chat_history[-max_messages:]

    try:
        # Build conversation string
        lines = []
        for msg in recent:
            # print("msg: ", msg)
            role = msg.role
            content = msg.content
            lines.append(f"{role}: {content} ")

        conversation = "\n".join(lines)

        # Count tokens
        encoding = tiktoken.encoding_for_model("gpt-4")
        token_count = len(encoding.encode(conversation))

        if token_count <= MAX_TOKEN_COUNT:
            logger.info(
                f"Token count <= {MAX_TOKEN_COUNT}, returning conversation as-is"
            )
            return conversation

        # If over 5000 tokens, summarize
        logger.info(f"Token count > {MAX_TOKEN_COUNT}, generating summary")
        llm = OpenAI(
            model=SUMMARY_MODEL,
            temperature=0,
            api_key=settings.OPENAI_API_KEY,
            timeout=10,
            max_retries=1,
        )

        prompt = f"""Summarize this conversation - what is the user looking for and what details matter:

{conversation}

Summary:"""

        response = await llm.acomplete(prompt)
        summary = response.text.strip()

        logger.debug(f"Summary: {summary[:100]}...")
        return summary

    except Exception as e:
        logger.warning(f"Processing failed: {e}")
        # Return conversation string on error
        return conversation if "conversation" in locals() else None
