"""
Adapter to make workflow-based agents compatible with the chat engine interface.
This bridges the gap between the new AgentWorkflow API and the legacy chat interface.
"""

from typing import List, Optional
import asyncio
from app.core.environment_flags import is_development
from app.core.logging_config import get_logger
from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.llms import ChatMessage
from llama_index.core.chat_engine.types import (
    AgentChatResponse,
    StreamingAgentChatResponse,
)
from llama_index.core.agent.workflow.workflow_events import (
    AgentOutput,
    AgentStream,
    ToolCall,
    ToolCallResult,
)
from llama_index.core.workflow import Context
from llama_index.core.callbacks.schema import CBEventType
from llama_index.core.tools import ToolOutput

logger = get_logger(__name__)


class WorkflowAgentChatAdapter:
    """
    Adapter that provides achat/astream_chat interface for workflow agents.
    Integrates with EventCallbackHandler to maintain compatibility with existing event tracking.

    This adapter bridges the gap between:
    - Old API: AgentRunner with achat/astream_chat methods
    - New API: AgentWorkflow with run() and stream_events()

    Future Improvements:
    - Add support for source_nodes extraction from tool outputs
    - Implement retry logic for failed tool calls
    - Add metrics/telemetry for agent performance tracking
    - Support for custom event transformers
    - Better handling of multi-turn conversations with memory persistence
    """

    def __init__(self, agent_workflow: AgentWorkflow, event_handlers=None):
        self.agent_workflow = agent_workflow
        self.event_handlers = event_handlers or []
        self.context = Context(self.agent_workflow)

    async def achat(
        self, message: str, chat_history: Optional[List[ChatMessage]] = None
    ) -> AgentChatResponse:
        """
        Async chat interface that waits for complete response.

        Args:
            message: The user message to send to the agent
            chat_history: Optional list of previous chat messages for context

        Returns:
            AgentChatResponse with the complete response and sources
        """
        try:
            if is_development():
                handler = self.agent_workflow.run(
                    user_msg=message, chat_history=chat_history or [], ctx=self.context
                )
            else:
                handler = self.agent_workflow.run(
                    user_msg=message,
                    chat_history=chat_history or [],
                )

            result: AgentOutput = await handler

            # Extract tool outputs if available
            tool_outputs = []
            if hasattr(result, "tool_calls") and result.tool_calls:
                for tool_call in result.tool_calls:
                    if hasattr(tool_call, "tool_output"):
                        tool_outputs.append(tool_call.tool_output)

            # NOTE: Don't pass source_nodes explicitly - let AgentChatResponse.__post_init__
            # call set_source_nodes() to extract them from sources automatically
            return AgentChatResponse(
                response=result.response.content or "",
                sources=tool_outputs if tool_outputs else [],
            )
        except Exception as e:
            logger.exception(f"Error in achat: {e}")
            # Return error response instead of crashing
            return AgentChatResponse(
                response=f"I encountered an error while processing your request: {str(e)}",
                sources=[],
            )

    async def astream_chat(
        self, message: str, chat_history: Optional[List[ChatMessage]] = None
    ) -> StreamingAgentChatResponse:
        """
        Async streaming chat interface with event handling.

        Converts workflow events to streaming response and emits callback events
        for compatibility with the existing EventCallbackHandler system.

        Args:
            message: The user message to send to the agent
            chat_history: Optional list of previous chat messages for context

        Returns:
            StreamingAgentChatResponse that yields tokens as they're generated

        Note:
            This adapter handles the following workflow events:
            - ToolCall: Emits FUNCTION_CALL callback event
            - ToolCallResult: Emits AGENT_STEP callback event with tool output
            - AgentStream: Streams text deltas to the response queue
            - AgentOutput: Handles final/fallback response if no streaming occurred
        """
        handler = self.agent_workflow.run(
            user_msg=message, chat_history=chat_history or [], ctx=self.context
        )

        # Create a streaming response object
        streaming_response = StreamingAgentChatResponse()
        streaming_response._ensure_async_setup()

        # Create a background task to process the workflow stream
        async def process_stream():
            full_response = ""
            tool_outputs = []

            try:
                current_agent = None
                async for event in handler.stream_events():
                    # Handle ToolCall events
                    if (
                        hasattr(event, "current_agent_name")
                        and event.current_agent_name != current_agent
                    ):
                        current_agent = event.current_agent_name
                        # logger.info(f"\n{70* '='}\n [CURRENT AGENT] {current_agent} \n{70* '='}\n")
                        logger.info(f"\n [CURRENT AGENT] {current_agent}")

                    if isinstance(event, ToolCall):
                        logger.debug(
                            f"Tool call: {event.tool_name} with args: {event.tool_kwargs}"
                        )
                        # Emit function_call event for compatibility
                        for handler_obj in self.event_handlers:
                            try:
                                handler_obj.on_event_start(
                                    event_type=CBEventType.FUNCTION_CALL,
                                    payload={
                                        "function_call": event.tool_kwargs,
                                        "tool": type(
                                            "Tool",
                                            (),
                                            {
                                                "name": event.tool_name,
                                                "metadata": type(
                                                    "Metadata",
                                                    (),
                                                    {"name": event.tool_name},
                                                )(),
                                            },
                                        )(),
                                    },
                                    event_id=event.tool_id or "",
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Error emitting function_call event: {e}"
                                )

                    # Handle ToolCallResult events
                    elif isinstance(event, ToolCallResult):
                        logger.debug(f"Tool result from {event.tool_name}")
                        # Convert to ToolOutput for compatibility
                        tool_output = ToolOutput(
                            content=str(event.tool_output.content),
                            tool_name=event.tool_name,
                            raw_input=event.tool_kwargs,
                            raw_output=event.tool_output.raw_output,
                            is_error=event.tool_output.is_error,
                        )
                        tool_outputs.append(tool_output)

                        # CRITICAL: Update sources immediately so VercelStreamResponse can access them
                        streaming_response.sources = tool_outputs.copy()
                        streaming_response.set_source_nodes()
                        logger.debug(
                            f"Updated source_nodes: {len(streaming_response.source_nodes)} nodes"
                        )

                        # Emit agent_step event with tool response
                        for handler_obj in self.event_handlers:
                            try:
                                handler_obj.on_event_end(
                                    event_type=CBEventType.AGENT_STEP,
                                    payload={
                                        "response": type(
                                            "Response", (), {"sources": [tool_output]}
                                        )()
                                    },
                                    event_id=event.tool_id or "",
                                )
                            except Exception as e:
                                logger.warning(f"Error emitting agent_step event: {e}")

                    # Handle AgentStream events (streaming text)
                    elif isinstance(event, AgentStream):
                        if event.delta:
                            streaming_response.aput_in_queue(event.delta)
                            full_response += event.delta

                    # Handle AgentOutput events (final or intermediate responses)
                    elif isinstance(event, AgentOutput):
                        logger.debug("Received AgentOutput event")
                        if (
                            hasattr(event.response, "content")
                            and event.response.content
                        ):
                            # If we haven't streamed anything yet, put the full response
                            if not full_response:
                                content = event.response.content
                                # Stream the response word by word for better UX
                                words = content.split(" ")
                                for i, word in enumerate(words):
                                    token = word + (" " if i < len(words) - 1 else "")
                                    streaming_response.aput_in_queue(token)
                                    full_response += token

                # Get the final result
                result: AgentOutput = await handler

                # Update the streaming response with final data
                streaming_response.response = result.response.content or full_response

                # Update sources one final time (in case any were added at the end)
                if len(tool_outputs) > len(streaming_response.sources):
                    streaming_response.sources = tool_outputs
                    streaming_response.set_source_nodes()

                logger.debug(
                    f"Stream completed. Response length: {len(streaming_response.response)}, "
                    f"Sources: {len(streaming_response.sources)}, "
                    f"Source nodes: {len(streaming_response.source_nodes)}"
                )

            except Exception as e:
                logger.exception(f"Error in stream processing: {e}")
                streaming_response.exception = e
                raise
            finally:
                # Mark all event handlers as done
                for handler_obj in self.event_handlers:
                    if hasattr(handler_obj, "is_done"):
                        handler_obj.is_done = True

                streaming_response.is_done = True

        # Start the background task
        streaming_response.awrite_response_to_history_task = asyncio.create_task(
            process_stream()
        )

        return streaming_response
