import asyncio
import json
from app.core.logging_config import get_logger
from typing import Awaitable, List

from aiostream import stream
from fastapi import BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from llama_index.core.chat_engine.types import StreamingAgentChatResponse
from llama_index.core.llms import MessageRole
from typing import Optional
from app.services.chatbot.events import EventCallbackHandler
from app.schemas.chat import ChatData, Message, SourceNodes
from app.services.chatbot.suggestion import NextQuestionSuggestion
from app.services.chat_history.storage_interface import ChatHistoryStorage
from app.services.chat_history.message_saver import save_chat_messages
from app.core.environment_flags import is_development

logger = get_logger(__name__)


class VercelStreamResponse(StreamingResponse):
    """
    Class to convert the response from the chat engine to the streaming format expected by Vercel
    """

    TEXT_PREFIX = "0:"
    DATA_PREFIX = "8:"
    ERROR_PREFIX = "3:"

    def __init__(
        self,
        request: Request,
        event_handler: EventCallbackHandler,
        response: Awaitable[StreamingAgentChatResponse],
        chat_data: ChatData,
        background_tasks: BackgroundTasks,
        user_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        storage: Optional[ChatHistoryStorage] = None,
    ):
        content = VercelStreamResponse.content_generator(
            request,
            event_handler,
            response,
            chat_data,
            background_tasks,
            user_id=user_id,
            chat_id=chat_id,
            storage=storage,
        )
        super().__init__(content=content)

    @classmethod
    async def content_generator(
        cls,
        request: Request,
        event_handler: EventCallbackHandler,
        response: Awaitable[StreamingAgentChatResponse],
        chat_data: ChatData,
        background_tasks: BackgroundTasks,
        user_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        storage: Optional[ChatHistoryStorage] = None,
    ):
        chat_response_generator = cls._chat_response_generator(
            response,
            background_tasks,
            event_handler,
            chat_data,
            user_id=user_id,
            chat_id=chat_id,
            storage=storage,
        )
        event_generator = cls._event_generator(event_handler)

        # Merge the chat response generator and the event generator
        combine = stream.merge(chat_response_generator, event_generator)
        is_stream_started = False
        try:
            async with combine.stream() as streamer:
                async for output in streamer:
                    if await request.is_disconnected():
                        break

                    if not is_stream_started:
                        is_stream_started = True
                        # Stream a blank message to start displaying the response in the UI
                        yield cls.convert_text("")

                    yield output
        except Exception:
            logger.exception("Error in stream response")
            yield cls.convert_error(
                "An unexpected error occurred while processing your request, preventing the creation of a final answer. Please try again."
            )
        finally:
            # Ensure event handler is marked as done even if connection breaks
            event_handler.is_done = True

    @classmethod
    async def _event_generator(cls, event_handler: EventCallbackHandler):
        """
        Yield the events from the event handler
        """
        async for event in event_handler.async_event_gen():
            event_response = event.to_response()
            if event_response is not None:
                yield cls.convert_data(event_response)

    @classmethod
    async def _chat_response_generator(
        cls,
        response: Awaitable[StreamingAgentChatResponse],
        background_tasks: BackgroundTasks,
        event_handler: EventCallbackHandler,
        chat_data: ChatData,
        user_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        storage: Optional[ChatHistoryStorage] = None,
    ):
        """
        Yield the text response and source nodes from the chat engine.
        Also tracks messages for saving to chat history.
        """
        # Track messages for saving
        messages_chatdata: List[Message] = []
        messages_payload: List[dict] = []

        # Get the last user message (the one that triggered this response)
        last_user_message = None
        if chat_data.messages:
            for msg in reversed(chat_data.messages):
                if msg.role.value == "user":
                    last_user_message = msg
                    break

        # Determine session type once
        session_type = chat_data.get_session_type()

        # If this is a new chat (no chat_id), synchronously create the chat session
        # so we can emit the chat_id to the client and use it for subsequent saves.
        if user_id and storage and chat_id is None:
            try:
                # Derive a reasonable title from the last user message if available
                title = "New Chat"
                if last_user_message and last_user_message.content:
                    if is_development():
                        candidate = last_user_message.content.strip()[:80]
                    else:
                        candidate = last_user_message.content.strip()[:50]
                    candidate = " ".join(candidate.split())
                    if candidate:
                        title = candidate

                chat_session = await storage.create_chat(
                    user_id=user_id,
                    session_type=session_type,
                    title=title,
                )
                chat_id = chat_session.id
                logger.info(f"Created new chat {chat_id} for user {user_id} in stream")

                # Emit a metadata event so the frontend learns the new chat_id
                yield cls.convert_data(
                    {
                        "type": "chat_session",
                        "data": {
                            "chat_id": chat_id,
                        },
                    }
                )
            except Exception:
                # Log but continue streaming; chat history saving may be skipped
                logger.exception("Error creating chat session for new conversation")

        # Wait for the response from the chat engine
        result = await response

        # Once we got a source node, start a background task to download the files (if needed)
        # cls._process_response_nodes(result.source_nodes, background_tasks)

        # Wait for source nodes to be populated by the background task
        # This is necessary because the agent adapter populates source_nodes asynchronously
        max_wait_time = (
            5  # Maximum 5 seconds to wait for source nodes (reduced from 30)
        )
        wait_interval = 0.05  # Check every 50ms (increased frequency)
        elapsed_time = 0
        sources_found = False

        while not result.source_nodes and elapsed_time < max_wait_time:
            await asyncio.sleep(wait_interval)
            elapsed_time += wait_interval

            # Check if the stream has started producing tokens or sources are available
            if hasattr(result, "sources") and result.sources:
                sources_found = True
                # Force update source_nodes from sources if not already done
                if hasattr(result, "set_source_nodes"):
                    result.set_source_nodes()
                # If still no source_nodes after setting, break early (sources might not have nodes)
                if not result.source_nodes:
                    logger.debug(
                        "Sources found but no extractable source_nodes, continuing without wait"
                    )
                    break
                break

            # If stream has started producing content without sources, tools weren't called
            # No need to wait the full timeout
            if hasattr(result, "_queue") and not result._queue.empty():
                logger.debug("Stream started without sources, continuing without wait")
                break

        if result.source_nodes:
            logger.debug(
                f"Source nodes available after {elapsed_time:.2f}s: {len(result.source_nodes)} nodes"
            )
        elif sources_found:
            logger.debug(
                f"Sources found but no source nodes after {elapsed_time:.2f}s - sources may not contain retrievable nodes"
            )
        else:
            logger.debug(
                f"No source nodes available after waiting {elapsed_time:.2f}s (likely no tools were called)"
            )

        # Yield the source nodes
        yield cls.convert_data(
            {
                "type": "sources",
                "data": {
                    "nodes": [
                        SourceNodes.from_source_node(node).model_dump()
                        for node in result.source_nodes
                    ]
                },
            }
        )

        final_response = ""
        async for token in result.async_response_gen():
            final_response += token
            yield cls.convert_text(token)

        # Collect annotations from source nodes and events
        annotations = []

        # Build source nodes annotation if available
        if result.source_nodes:
            source_annotation = {
                "type": "sources",
                "data": {
                    "nodes": [
                        SourceNodes.from_source_node(node).model_dump()
                        for node in result.source_nodes
                    ]
                },
            }
            annotations.append(source_annotation)

        # Append captured tool outputs (e.g., CSV generation results) to annotations
        if (
            hasattr(event_handler, "captured_tool_outputs")
            and event_handler.captured_tool_outputs
        ):
            annotations.extend(event_handler.captured_tool_outputs)

        # Note: Tool annotations are streamed to client and will be included
        # when client sends the message back. For now, we save basic annotations.

        # Save messages if user_id and storage are provided
        if user_id and storage and last_user_message and chat_id:
            try:
                # Build user message in both formats
                user_msg_chatdata = Message(
                    role=last_user_message.role,
                    content=last_user_message.content,
                    annotations=last_user_message.annotations,
                )
                messages_chatdata.append(user_msg_chatdata)

                # User message in payload format (preserve parts if present)
                user_msg_payload = {
                    "role": last_user_message.role.value,
                    "content": last_user_message.content,
                    "annotations": [
                        ann.model_dump() if hasattr(ann, "model_dump") else ann
                        for ann in (last_user_message.annotations or [])
                    ]
                    if last_user_message.annotations
                    else None,
                    "parts": last_user_message.parts,  # Preserve parts from client
                }
                messages_payload.append(user_msg_payload)

                # Build assistant message in both formats
                assistant_msg_chatdata = Message(
                    role=MessageRole.ASSISTANT,
                    content=final_response,
                    annotations=annotations if annotations else None,
                )
                messages_chatdata.append(assistant_msg_chatdata)

                # Assistant message in payload format
                assistant_msg_payload = {
                    "role": "assistant",
                    "content": final_response,
                    "annotations": [
                        ann if isinstance(ann, dict) else ann.model_dump()
                        for ann in annotations
                    ]
                    if annotations
                    else None,
                    "parts": [
                        {"type": "text", "text": final_response}
                    ],  # Generate parts for assistant
                }
                messages_payload.append(assistant_msg_payload)

                # Save messages in background
                if messages_chatdata and messages_payload:
                    background_tasks.add_task(
                        save_chat_messages,
                        storage=storage,
                        user_id=user_id,
                        chat_id=chat_id,
                        messages_chatdata=messages_chatdata,
                        messages_payload=messages_payload,
                    )
            except Exception as e:
                # Log but don't fail the request
                logger.exception(f"Error preparing messages for saving: {e}")

        # Generate next questions if next question prompt is configured
        # question_data = await cls._generate_next_questions(
        #     chat_data.messages, final_response
        # )
        # if question_data:
        #     yield cls.convert_data(question_data)

        # the text_generator is the leading stream, once it's finished, also finish the event stream
        event_handler.is_done = True

    @classmethod
    def convert_text(cls, token: str):
        # Escape newlines and double quotes to avoid breaking the stream
        token = json.dumps(token)
        return f"{cls.TEXT_PREFIX}{token}\n"

    @classmethod
    def convert_data(cls, data: dict):
        data_str = json.dumps(data)
        return f"{cls.DATA_PREFIX}[{data_str}]\n"

    @classmethod
    def convert_error(cls, error: str):
        error_str = json.dumps(error)
        return f"{cls.ERROR_PREFIX}{error_str}\n"

    @staticmethod
    async def _generate_next_questions(chat_history: List[Message], response: str):
        questions = await NextQuestionSuggestion.suggest_next_questions(
            chat_history, response
        )
        if questions:
            return {
                "type": "suggested_questions",
                "data": questions,
            }
        return None
